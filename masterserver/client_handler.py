import re
from asyncio import StreamReader, StreamWriter

from . import get_logger

from typing import TYPE_CHECKING

from .exceptions import CommandError, InvalidCommandError, UnknownCommandError

if TYPE_CHECKING:
    from masterserver import MasterServer
    from masterserver.red_eclipse_server import RedEclipseServer


class ClientHandlerBase:
    _logger = get_logger("master-server-client")

    def __init__(self, master_server: "MasterServer", reader: StreamReader, writer: StreamWriter):
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer
        self._master_server = master_server

        self._client_data = self._writer.get_extra_info("peername")

    async def handle_generic_connection(self):
        raise NotImplementedError()


class ClientHandler(ClientHandlerBase):
    async def _handle_update_command(self):
        lines = [
            "setversion 160 230",
            "clearservers",
        ]

        server: RedEclipseServer
        for server in self._master_server.servers:
            lines.append("addserver %s" % server.addserver_line())

        response = "\n".join(lines)
        response += "\n"

        self._writer.write(response.encode("cube2"))

        self._logger.info("closing connection from client %r", self._client_data)

    async def _handle_server(self, first_command: str):
        re_server = None

        command = first_command

        while True:
            if not command:
                # the connection will be cleaned up by the caller, therefore we just have to clean up the server entry
                self._logger.warning("Lost connection to client %r, closing", self._client_data)

                if re_server is not None:
                    if await self._master_server.remove_server(re_server):
                        self._logger.info("removed server %r", re_server)

                return

            elif command.startswith("server "):
                match = re.match(r'server ([0-9]+) ([^\s]+) ([0-9]+) "([^"]*)" ([0-9]+) "([^"]*)"', command)

                if not match:
                    raise InvalidCommandError(command)

                host, _ = self._writer.get_extra_info("peername")
                port, serverip, version, _, _, branch = match.groups()

                self._logger.info("Received registration request for server %s:%d", host, int(port))

                # try to register server
                # if the registration fails, we'll receive None as return value
                re_server = await self._master_server.register_server(host, serverip, int(port), branch)

                if re_server is not None:
                    reply = "Successfully pinged (%s:%d), server is now listed" % (re_server.ip_addr, re_server.port)
                else:
                    reply = "Error: Pinging failed, server will not be listed"

                self._writer.write('echo "{}"\n'.format(reply).encode("cube2"))

                command = (await self._reader.readline()).decode().rstrip("\n")

            raise UnknownCommandError(command)

    async def handle_generic_connection(self):
        try:
            self._logger.info("client connected: %r", self._client_data)

            first_command = (await self._reader.readline()).decode().rstrip("\n")

            # nagios-like monitoring for instance just probe whether the port is available, and send no message
            if first_command.strip(" \r\n") == "":
                self._logger.warning("no command received from client, closing connection")

            elif first_command == "update":
                await self._handle_update_command()

            # server try to keep up their TCP connection
            # the reason upstream is probably rate limiting, but here it's planned to implement rate limiting by
            # limiting the amount of servers in the server list rather than closing new connections
            # in any case we can run the specific handler from here, the try-finally will clean up the connection
            elif first_command.startswith("server "):
                await self._handle_server(first_command)

        except CommandError as e:
            self._logger.warning(
                "unknown or invalid command \"%s\" from client %r, closing connection",
                e.command,
                self._client_data
            )

        finally:
            self._writer.close()
            await self._writer.wait_closed()
