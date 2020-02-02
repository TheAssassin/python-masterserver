from ipaddress import IPv4Address

import typing

if typing.TYPE_CHECKING:
    from .remote_master_server import RemoteMasterServer


class RedEclipseServer:
    """
    Red Eclipse Server representation
    """

    def __init__(self, ip_addr: str, port: int, priority: int, description: str, handle: str, role: str, branch: str,
                 remote_master_server: "RemoteMasterServer" = None, ping_addr: str = None):
        self.ip_addr: IPv4Address = IPv4Address(ip_addr)
        self.port: int = int(port)
        self.priority: int = int(priority)
        self.description: str = description
        self.auth_handle: str = handle
        self.role: str = role
        self.branch: str = branch
        self.remote_master_server: RemoteMasterServer = remote_master_server

        if not ping_addr:
            ping_addr = ip_addr

        self.ping_addr: IPv4Address = IPv4Address(ping_addr)

    def addserver_str(self):
        return '%s %d %d "%s" "%s" "%s" "%s"' % (
            self.ip_addr,
            self.port,
            self.priority,
            self.description,
            self.auth_handle,
            self.role,
            self.branch
        )

    def __repr__(self):
        return "<RedEclipseServer %s>" % self.addserver_str()

    def __eq__(self, other: "RedEclipseServer"):
        return self.ip_addr == other.ip_addr and self.port == other.port

    def to_json_dict(self) -> dict:
        rv = {
            "ip_addr": self.ip_addr.exploded,
            "port": self.port,
            "priority": self.priority,
            "description": self.description,
            "auth_handle": self.auth_handle,
            "role": self.role,
            "branch": self.branch,
            "remote_master_server": None,
        }

        if self.remote_master_server is not None:
            rv["remote_master_server"] = "%s:%d" % (self.remote_master_server.host, self.remote_master_server.port)

        return rv
