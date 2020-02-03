import asyncio
import itertools
from asyncio import StreamReader, StreamWriter, Lock
from ipaddress import IPv4Address, AddressValueError
from typing import List, Tuple

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

        self._started: bool = False

    def add_server_to_proxy(self, host: str, port: int = 28800):
        self._proxied_master_servers.append((host, port))

    async def _handle_connection(self, reader: StreamReader, writer: StreamWriter):
        self._logger.debug("client connteced")
        msc = ClientHandler(self, reader, writer)
        await msc.handle()

    async def _poll_proxied_servers(self):
        while True:
            proxied_servers = [RemoteMasterServer(host, port) for host, port in self._proxied_master_servers]

            self._logger.info("updating from proxied servers %r", proxied_servers)

            results = await asyncio.gather(*[
                proxied_server.list_servers() for proxied_server in proxied_servers
            ])

            servers: List[RedEclipseServer] = list(itertools.chain.from_iterable(results))

            await asyncio.gather(*[self._add_or_update_server(server) for server in servers])

            await asyncio.sleep(60)

    async def start_server(self):
        if self._started:
            raise RuntimeError("Server already started")

        self._logger.info("Starting masterserver")

        await asyncio.start_server(self._handle_connection, port=self._port)

        loop = asyncio.get_event_loop()
        loop.create_task(self._poll_proxied_servers())
        loop.create_task(self._ping_all_servers())

        self._started = True

    @property
    def servers(self) -> List[RedEclipseServer]:
        # make sure to return a copy, we don't want modifications to propagate into the database
        return list(self._servers)

    async def _ping_all_servers(self):
        async def ping_task(server: RedEclipseServer):
            pinger = ServerPinger(server.ip_addr, server.port+1)

            try:
                await pinger.ping()
            except TimeoutError:
                self._logger.warning("Pinging server %r failed, removing", server)
                return server

        while True:
            self._logger.info("Pinging servers")

            # fetch current list of servers; no need to block any additions of servers, they'll be handled later
            # anyway
            async with self._lock:
                servers = self.servers

            # create a ping task for each
            tasks = [ping_task(server) for server in servers]

            # run the pings and collect the results
            # the resulting list will be a mix of None and servers to be removed (as the ping task returns its server
            # in case it has to be removed)
            servers_to_remove = list(filter(lambda i: i is not None, await asyncio.gather(*tasks)))

            # lock state and remove servers we couldn't reach
            async with self._lock:
                for server in servers_to_remove:
                    self._servers.remove(server)
                transaction.commit()

            self._logger.info("Ping done")

            await asyncio.sleep(60)

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
