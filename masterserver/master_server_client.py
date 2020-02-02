import re
from asyncio import StreamReader, StreamWriter

from . import get_logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from masterserver import MasterServer
    from masterserver.red_eclipse_server import RedEclipseServer


class MasterServerClient:
    _logger = get_logger("master-server-client")

    def __init__(self, master_server: "MasterServer", reader: StreamReader, writer: StreamWriter):
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer
        self._master_server = master_server

    async def handle(self):
        client = self._writer.get_extra_info("peername")

        self._logger.info("client connected: %r", client)

        command = (await self._reader.readline()).decode().rstrip("\n")

        if command == "update":
            lines = [
                "setversion 160 230",
                "clearservers",
            ]

            server: RedEclipseServer
            for server in self._master_server.servers:
                lines.append("addserver %s" % server.addserver_str())

            response = "\n".join(lines)
            response += "\n"

            self._writer.write(response.encode("cube2"))

            self._logger.info("closing connection from client %r", client)
            self._writer.close()

        elif command.startswith("server "):
            re_server = None

            while True:
                if not command:
                    self._logger.warning("Lost connection to client %r, closing", client)
                    self._writer.close()
                    await self._writer.wait_closed()

                    if re_server is not None:
                        if await self._master_server.remove_server(re_server):
                            self._logger.info("removed server %r", re_server)

                    return

                match = re.match(r'server ([0-9]+) ([^\s]+) ([0-9]+) "([^"]*)" ([0-9]+) "([^"]*)"', command)

                if not match:
                    raise ValueError("Invalid server command", command)

                host, _ = self._writer.get_extra_info("peername")
                port, _, version, _, _, branch = match.groups()

                self._logger.info("Received registration request for server %s:%d", host, int(port))

                re_server = await self._master_server.register_server(host, int(port), int(version), branch)

                command = (await self._reader.readline()).decode().rstrip("\n")

        else:
            self._logger.error("unknown command %s from client %r, closing connection", command, client)
            self._writer.close()
            await self._writer.wait_closed()
            return
