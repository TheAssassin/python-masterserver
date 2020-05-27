import asyncio
import itertools
import sys
from asyncio import StreamReader, StreamWriter, Lock, AbstractServer, Task
from ipaddress import IPv4Address, AddressValueError
from typing import List, Tuple, Union, Set

from . import get_logger
from .client_handler import ClientHandler
from .parsed_query_reply import ParsedQueryReply
from .red_eclipse_server import RedEclipseServer
from .remote_master_server import RemoteMasterServer
from .server_pinger import ServerPinger, PingError


class MasterServer:
    _logger = get_logger()

    def __init__(self, port: int = None, backup_file: str = None):
        self._proxied_master_servers: List[Tuple[str, int]] = []

        # # FIXME: use set, should save some annoying list comparisons
        # self._servers: List[RedEclipseServer] = []
        self._lock = Lock()

        if port is None:
            port = 28800

        self._port: int = port

        # keep track of state of server
        # this way, we can run instances for testing
        self._started: bool = False
        self._stopped: bool = False
        self._running_server: Union[AbstractServer, None] = None
        self._running_tasks: Set[Task] = set()

        self._servers: Set[RedEclipseServer] = set()

        # we store a backup of server:port pairs in this file every n seconds
        # on startup, when the proxied master servers haven't been contacted yet and "own" servers have not registered
        # yet, we can use those servers, ping them and this way restore the state of the master server
        # will be slightly out of date (<= n seconds) but that's not really an issue for a master server
        self._backup_file_path: str = backup_file
        self._backup_interval: int = 60

    @property
    def port(self):
        return self._port

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
            proxied_servers = [RemoteMasterServer(host, port) for host, port in self._proxied_master_servers]

            self._logger.info("updating from proxied servers %r", proxied_servers)

            tasks = [proxied_server.list_servers() for proxied_server in proxied_servers]

            results = await asyncio.gather(*tasks)

            servers: List[RedEclipseServer] = list(itertools.chain.from_iterable(results))

            await asyncio.gather(*[self._add_or_update_server(server) for server in servers])

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

        # start server
        self._running_server = await asyncio.start_server(self._handle_connection, port=self._port)

        # restore state
        if self._backup_file_path is None:
            self._logger.warning("No backup file path provided, will not back up own state")

        else:
            try:
                with open(self._backup_file_path) as f:
                    self._logger.info("Reading backed up servers from file %s", self._backup_file_path)

                    # keep track of count for logging purposes (that's the only reason, I promise!)
                    servers_count = 0

                    for line in f:
                        ip_addr, port = line.split(":")
                        await self._add_or_update_server(RedEclipseServer(ip_addr, port, 0, "", "", "", ""))
                        servers_count += 1

                    if servers_count <= 0:
                        self._logger.warning("Backup file contains no data, no state to restore")

                    self._logger.info("Restore complete")

            except OSError:
                self._logger.warning("Backup file %s not found, cannot restore state", self._backup_file_path)

            except:  # noqa: E722
                self._logger.exception(
                    "Failed to read backup, cannot restore state from file %s",
                    self._backup_file_path
                )

        # start background tasks
        self._logger.info("Starting background tasks")
        self._running_tasks.add(self._create_task(self._poll_proxied_servers, 60))
        self._running_tasks.add(self._create_task(self._ping_and_update_all_servers, 60))

        if self._backup_file_path is not None:
            self._running_tasks.add(self._create_task(self._backup_state, self._backup_interval))

        self._started = True
        self._stopped = False

    async def stop_server(self):
        if self._stopped:
            raise RuntimeError("Server already stopped")

        if not self._started:
            raise RuntimeError("Server has not been started")

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
    def servers(self) -> Set[RedEclipseServer]:
        # make sure to return a copy, we don't want modifications to propagate into the database
        return set(self._servers)

    def _create_task(self, callback: callable, interval: int, event_loop: asyncio.AbstractEventLoop = None):
        """
        Creates a task that runs a given callback at a given interval. Logs exceptions instead of just crashing
        silently.

        :param callback: callback to call every interval seconds
        :param interval: interval in which to call the task; uses sleep internally, so there's no precise timing to be
            expected
        :return: created task
        """

        if event_loop is None:
            event_loop = asyncio.get_event_loop()

        async def wrapper(*args, **kwargs):
            while True:
                try:
                    await callback(*args, **kwargs)
                except:  # noqa: E722
                    self._logger.exception("Error in task %s", callback.__name__)

                await asyncio.sleep(interval)

        return event_loop.create_task(wrapper())

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

            except Exception as e:
                if isinstance(e, TimeoutError):
                    self._logger.warning("Ping timeout for server %r, removing", server)
                elif isinstance(e, PingError):
                    self._logger.warning("Pinging failed for server %r (%s), removing", server, str(e))
                else:
                    self._logger.critical("Ping failed with unknown error %r", e, exc_info=sys.exc_info())

                self._logger.debug("Exception information for %r" % e, exc_info=sys.exc_info())

                return server, False

            # apply the description sent by the server
            parsed = ParsedQueryReply(data)
            server.description = parsed.description

            return server, True

        # store tasks to be able to clean them up properly in case this task has been canceled
        tasks = []

        try:
            self._logger.info("Pinging servers")

            # fetch current list of servers; no need to block any additions of servers, they'll be handled later
            # anyway
            async with self._lock:
                # need to copy the value
                servers = list(self.servers)

            # create a ping task for each
            tasks = [ping_task(server) for server in servers]

            # run the pings and collect the results
            # the resulting list will contain (updated) server objects as well as whether the ping was successful
            ping_results = list(await asyncio.gather(*tasks))

            # lock state and remove servers we couldn't reach
            async with self._lock:
                server: RedEclipseServer
                for server, ping_successful in ping_results:
                    # servers is a set, therefore to replace it we have to remote the old one and then add
                    # the new instance
                    self._logger.debug("[ping] removing %r", server.remote_master_server)
                    self._servers.remove(server)

                    if ping_successful:
                        self._logger.debug("[ping] adding %r", server)
                        self._servers.add(server)

            self._logger.info("Ping done")

        except asyncio.CancelledError:
            self._logger.info("ping and update task cancelled")

            for task in tasks:
                task.close()
                await task

    async def _backup_state(self):
        async with self._lock:
            self._logger.info("Backing up state to file %s", self._backup_file_path)

            with open(self._backup_file_path, "w") as f:
                for server in self._servers:
                    f.write("%s:%d\n" % (server.ip_addr.exploded, server.port))

    async def _add_or_update_server(self, server: RedEclipseServer):
        async with self._lock:
            # we can update existing servers; they will be pinged automatically by a background task
            for i, old_server in enumerate(self._servers):
                if server == old_server:
                    self._logger.debug("updating server %r", server)
                    self._servers.remove(server)
                    self._servers.add(server)
                    break

            # in case this is a new server, we need to ping it first before adding it
            else:
                self._logger.debug("trying to ping server %r", server)

                # "info port" is always server port plus one
                # FIXME: pinging should probably not lock
                pinger = ServerPinger(server.ip_addr, server.port + 1)

                try:
                    data = await pinger.ping()
                except TimeoutError:
                    self._logger.warning("ping timeout for server %r, server will not be listed", server)
                    return
                except PingError as e:
                    self._logger.warning("ping failed for server %r, server will not be listed: %s", server, e)
                    return

                # apply the description sent by the server
                parsed = ParsedQueryReply(data)
                server.description = parsed.description

                self._logger.info("ping successful, registered server %r", server)

                # make sure old server data is removed
                try:
                    self._servers.remove(server)
                except KeyError:
                    pass

                # if we don't remove before and just add the new server the old one is not replaced
                self._servers.add(server)

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

            return True
