from ipaddress import IPv4Address

import typing

if typing.TYPE_CHECKING:
    from .remote_master_server import RemoteMasterServer


class RedEclipseServer:
    """
    Red Eclipse Server representation
    """

    def __init__(self, ip_addr: str, port: int,
                 priority: int = 0, description: str = None, handle: str = None, role: str = None, branch: str = None,
                 remote_master_server: "RemoteMasterServer" = None):
        self._ip_addr: IPv4Address = IPv4Address(ip_addr)
        self._port: int = int(port)
        self._priority: int = int(priority)
        self._description: str = description
        self._auth_handle: str = handle
        self._role: str = role
        self._branch: str = branch
        self._remote_master_server: RemoteMasterServer = remote_master_server

    @property
    def ip_addr(self):
        return IPv4Address(self._ip_addr)

    @ip_addr.setter
    def ip_addr(self, new_addr: IPv4Address):
        if not self._ip_addr.is_private:
            raise ValueError("IP address may only be replaced if it's private")

        if new_addr.is_private:
            raise ValueError("IP address may only be overwritten by a non-private one")

        self._ip_addr = new_addr
        
    @property
    def port(self):
        return self._port
    
    @property
    def priority(self):
        return self._priority
    
    @property
    def description(self):
        # make sure every server has a description
        if not self._description:
            return "%s:[%d]" % (self.ip_addr.exploded, self.port)
        
        return self._description

    @description.setter
    def description(self, value):
        self._description = value
    
    @property
    def auth_handle(self):
        return self._auth_handle
    
    @property
    def role(self):
        return self._role
    
    @property
    def branch(self):
        return self._branch
    
    @property
    def remote_master_server(self):
        return self._remote_master_server

    def addserver_line(self):
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
        return "<RedEclipseServer %s>" % self.addserver_line()

    def __eq__(self, other: "RedEclipseServer"):
        return self.ip_addr == other.ip_addr and self.port == other.port

    def __hash__(self):
        return hash((self.ip_addr, self.port))

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
