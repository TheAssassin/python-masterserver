import re

from .red_eclipse_server import RedEclipseServer

import typing
if typing.TYPE_CHECKING:
    from .remote_master_server import RemoteMasterServer


class ServerListParser:
    def __init__(self, remote_master_server: "RemoteMasterServer"):
        self._remote_master_server = remote_master_server

    def parse_line(self, line: bytes):
        line.rstrip(b"\n")

        if not line.startswith(b"addserver"):
            return None

        match = re.match(rb'addserver ([0-9\.]+) ([0-9]+) ([0-9-]+) "([^"]+)" "([^"]*)" "([^"]*)" "([^"]*)"', line)

        if not match:
            raise ValueError("Invalid addserver response", line)

        return RedEclipseServer(*[i.decode("cube2") for i in match.groups()], remote_master_server=self._remote_master_server)
