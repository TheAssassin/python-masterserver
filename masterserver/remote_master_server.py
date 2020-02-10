import asyncio
from asyncio import StreamReader, StreamWriter

from . import get_logger
from .server_list_parser import ServerListParser


class RemoteMasterServer:
    _logger = get_logger("remote-master-server")

    def __init__(self, host: str, port: int = None):
        if port is None:
            port = 28800

        self._host: str = host
        self._port: int = port

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def __repr__(self):
        return "<RemoteMasterServer %s:%d>" % (self._host, self._port)

    async def connect(self) -> (StreamReader, StreamWriter):
        reader, writer = await asyncio.open_connection(self._host, self._port)
        return reader, writer

    async def list_servers(self):
        reader, writer = await self.connect()

        try:
            servers = []

            writer.write(b"update\n")

            parser = ServerListParser(self)

            while True:
                line = await reader.readline()

                if not line:
                    break

                try:
                    parsed = parser.parse_line(line)
                except ValueError as e:
                    self._logger.exception("Failed to parse addserver line", e)
                    continue

                if not parsed:
                    continue

                servers.append(parsed)

                return servers

        finally:
            writer.close()
            await writer.wait_closed()
