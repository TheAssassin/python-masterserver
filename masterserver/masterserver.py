import asyncio
import itertools
from asyncio import StreamReader, StreamWriter, Lock, AbstractServer, Task
from ipaddress import IPv4Address, AddressValueError
from typing import List, Tuple, Union, Set

import ZODB
import transaction
from persistent.list import PersistentList

from . import get_logger
from .client_handler import ClientHandler
from .parsed_query_reply import ParsedQueryReply
from .red_eclipse_server import RedEclipseServer
from .remote_master_server import RemoteMasterServer
from .server_pinger import ServerPinger


class MasterServer:
    _logger = get_logger()

    def __init__(self, port: int = None, database: str = None):
        self._proxied_master_servers: List[Tuple[str, int]] = []

        # # FIXME: use set, should save some annoying list comparisons
        # self._servers: List[RedEclipseServer] = []
        self._lock = Lock()

        if port is None:
            port = 28800

        self._port: int = port

        if not database:
            self._logger.warning("Using in-memory database")
        else:
            self._logger.warning("Using database %s", database)

        self._database: ZODB.DB = ZODB.connection(database)

        try:
            self._servers = self._database.root.servers
        except AttributeError:
            self._servers = self._database.root.servers = PersistentList()

        # keep track of state of server
        # this way, we can run instances for testing
        self._started: bool = False
        self._stopped: bool = False
        self._running_server: Union[AbstractServer, None] = None
        self._running_tasks: Set[Task] = set()

    def add_server_to_proxy(self, host: str, port: int = 28800):
        self._proxied_master_servers.append((host, port))

    async def _handle_connection(self, reader: StreamReader, writer: StreamWriter):
        self._logger.debug("client connteced")
        msc = ClientHandler(self, reader, writer)
        await msc.handle()

    async def _poll_proxied_servers(self):
        self._logger.info("proxied servers polling task started")

        # store tasks outside loop to be able to clean them up properly in case this task has been canceled
        tasks = []

        try:
            while True:
                proxied_servers = [RemoteMasterServer(host, port) for host, port in self._proxied_master_servers]

                self._logger.info("updating from proxied servers %r", proxied_servers)

                tasks = [proxied_server.list_servers() for proxied_server in proxied_servers]

                results = await asyncio.gather(*tasks)

                servers: List[RedEclipseServer] = list(itertools.chain.from_iterable(results))

                await asyncio.gather(*[self._add_or_update_server(server) for server in servers])

                await asyncio.sleep(60)

        except asyncio.CancelledError:
            self._logger.info("proxied servers polling task cancelled")

            for task in tasks:
                task.close()
                await task

    async def start_server(self):
        if self._started:
            raise RuntimeError("Server already started")

        if self._stopped:
            raise RuntimeError("Server already stopped")

        self._logger.info("Starting masterserver")

        # sanity checks
        assert self._running_server is None

        self._running_server = await asyncio.start_server(self._handle_connection, port=self._port)

        loop = asyncio.get_event_loop()
        self._running_tasks.add(loop.create_task(self._poll_proxied_servers()))
        self._running_tasks.add(loop.create_task(self._ping_and_update_all_servers()))

        self._started = True
        self._stopped = False

    async def stop_server(self):
        if not self._started:
            raise RuntimeError("Server has not been started")

        if self._stopped:
            raise RuntimeError("Server already stopped")

        self._logger.info("Stopping masterserver")

        # sanity check
        assert self._running_server is not None

        # cancel running tasks
        for t in self._running_tasks:
            t.cancel()

        # stop server
        self._running_server.close()
        await self._running_server.wait_closed()

        self._started = False
        self._stopped = True

    @property
    def servers(self) -> List[RedEclipseServer]:
        # make sure to return a copy, we don't want modifications to propagate into the database
        return list(self._servers)

    async def _ping_and_update_all_servers(self):
        async def ping_task(server: RedEclipseServer) -> Tuple[RedEclipseServer, bool]:
            """
            Pings a server and updates some data, e.g., the serverdesc, from the reply.

            :param server: server to ping (and update)
            :return: (updated) server and boolean indicating whether a reply was received (True means success)
            """

            pinger = ServerPinger(server.ip_addr, server.port+1)

            try:
                data = await pinger.ping()
            except TimeoutError:
                self._logger.warning("Pinging server %r failed, removing", server)
                return server, False

            # apply the description sent by the server
            parsed = ParsedQueryReply(data)
            server.description = parsed.description

            return server, True

        self._logger.info("ping and update task started")

        # store tasks outside loop to be able to clean them up properly in case this task has been canceled
        tasks = []

        try:
            while True:
                self._logger.info("Pinging servers")

                # fetch current list of servers; no need to block any additions of servers, they'll be handled later
                # anyway
                async with self._lock:
                    servers = self.servers

                # create a ping task for each
                tasks = [ping_task(server) for server in servers]

                # run the pings and collect the results
                # the resulting list will contain (updated) server objects as well as whether the ping was successful
                ping_results = list(await asyncio.gather(*tasks))

                # lock state and remove servers we couldn't reach
                async with self._lock:
                    for server, ping_successful in ping_results:
                        # we can simply remove the entire server and re-add it in case we could ping it
                        self._servers.remove(server)

                        if ping_successful:
                            self._servers.append(server)

                    transaction.commit()

                self._logger.info("Ping done")

                await asyncio.sleep(60)

        except asyncio.CancelledError:
            self._logger.info("ping and update task cancelled")

            for task in tasks:
                task.close()
                await task

    async def _add_or_update_server(self, server: RedEclipseServer):
        async with self._lock:
            # we can update existing servers; they will be pinged automatically by a background task
            for i, old_server in enumerate(self._servers):
                if server == old_server:
                    self._logger.debug("updating server %r", server)
                    self._servers[i] = server
                    break

            # in case this is a new server, we need to ping it first before adding it
            else:
                self._logger.debug("trying to ping server %r", server)

                # "info port" is always server port plus one
                # FIXME: pinging should probably not lock
                pinger = ServerPinger(server.ip_addr, server.port+1)

                try:
                    data = await pinger.ping()
                except TimeoutError:
                    self._logger.warning("ping timeout for server %r, server will not be listed", server)
                    return

                # apply the description sent by the server
                parsed = ParsedQueryReply(data)
                server.description = parsed.description

                self._logger.info("ping successful, registered server %r", server)

                self._servers.append(server)

            transaction.commit()

            return server

    async def register_server(self, host: str, serverip: str, port: int, branch: str):
        server = RedEclipseServer(host, port, 10, "%s:%d" % (host, port), "", "", branch)

        # sanitize value
        serverip = serverip.strip()

        # if a registration comes from a private IP range, we assume we can trust the IP they
        if IPv4Address(host).is_private and serverip and serverip != "*":
            self._logger.warning("Remote IP %s is in private address space, using serverip %s", host, serverip)

            try:
                server.ip_addr = IPv4Address(serverip)
            except AddressValueError:
                self._logger.error("Invalid IPv4 address %s, cannot fall back to serverip", serverip)

        return await self._add_or_update_server(server)

    async def remove_server(self, server: RedEclipseServer):
        async with self._lock:
            try:
                self._servers.remove(server)
            except ValueError:
                return False

            transaction.commit()
            return True
