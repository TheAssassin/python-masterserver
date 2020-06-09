import re
from asyncio import StreamReader, StreamWriter

from . import get_logger

from typing import TYPE_CHECKING, Dict

from .auth import AuthStorage, AuthRequest
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


class ServerClientHandler(ClientHandlerBase):
    """
    "Subhandler" for server connections. It doesn't handle generic connections, but provides a special handler method
    for server connections.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # the instance is kept alive while the server is connected to the master
        # once the connection is interrupted, all old requests become invalid automatically
        self._auth_requests: Dict[int, AuthRequest] = {}

    async def handle_server(self, first_command: str = None):
        # note for self: the connection is closed properly once this method returns (or raises an exception), no need
        # to close it here

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
                match = re.match(r'server ([0-9a-fA-F+-]+) ([^\s]+) ([0-9a-fA-F+-]+) "([^"]*)" ([0-9a-fA-F+-]+) "([^"]*)"', command)

                if not match:
                    raise InvalidCommandError(command)

                host, _ = self._writer.get_extra_info("peername")
                port, serverip, version, _, _, branch = match.groups()

                self._logger.info("Received registration request for server %s:%d", host, int(port))

                # try to register server
                # if the registration fails, we'll receive None as return value
                re_server = await self._master_server.register_server(host, serverip, int(port), branch)

                if re_server is not None:
                    reply = "Successfully pinged (%s:%d), server is now listed" % (
                        re_server.ip_addr, re_server.port
                    )

                else:
                    reply = "Error: Pinging failed, server will not be listed"

                self._writer.write('echo "{}"\n'.format(reply).encode("cube2"))

            elif command.startswith("reqauth "):
                match = re.match(r'reqauth ([0-9a-fA-F+-]+) ([^\s]+) ([^\s]+)', command)

                if not match:
                    raise InvalidCommandError(command)

                # request_index is used by the client to match the reply to the request
                # user_name is what we use to look up the pubkey in our user database
                # user_ip is not needed by us, and is discarded (TODO: don't forward user IPs to master server)
                request_id, user_name, user_ip = match.groups()

                try:
                    request_id = int(request_id)
                except ValueError:
                    raise InvalidCommandError(command)

                try:
                    auth_request = AuthStorage.generate_auth_challenge(user_name)

                except KeyError:
                    # we don't support authentication yet
                    # a protocol conform behavior is to just send auth failures for all requests
                    self._writer.write('failauth {}\n'.format(request_id).encode("cube2"))

                    self._logger.info("auth request no. %d failed for user %s on server %s: unknown user",
                        request_id,
                        user_name,
                        re_server.ip_addr
                    )

                else:
                    self._auth_requests[request_id] = auth_request
                    self._writer.write('chalauth {} {}\n'.format(request_id, auth_request.challenge).encode("cube2"))
                    self._logger.debug("Generated auth challenge for user {}, request ID {}: {}".format(
                        user_name, request_id, auth_request.challenge
                    ))

            elif command.startswith("confauth "):
                match = re.match(r'confauth ([0-9a-fA-F+-]+) ([^\s]+)', command)

                if not match:
                    raise InvalidCommandError(command)

                # request_index is used by the client to match the reply to the request
                # user_name is what we use to look up the pubkey in our user database
                # user_ip is not needed by us, and is discarded (TODO: don't forward user IPs to master server)
                request_id, reply = match.groups()

                try:
                    request_id = int(request_id)
                except ValueError:
                    raise InvalidCommandError(command)

                self._logger.debug("received {}".format(command))

                def fail_auth():
                    self._writer.write("failauth {}\n".format(request_id).encode("cube2"))
                    del self._auth_requests[request_id]

                try:
                    auth_request = self._auth_requests[request_id]

                except KeyError:
                    self._logger.error("received confauth for unknown request ID {}".format(request_id))
                    fail_auth()

                else:
                    if AuthStorage.validate_auth_reply(reply, auth_request):
                        flags = AuthStorage.get_user_flags(auth_request.user_name)

                        message = "succauth {} \"{}\" \"{}\"\n".format(request_id, auth_request.user_name, flags)
                        self._writer.write(message.encode("cube2"))

                        self._logger.info("auth succeeded {} [{}] ({}) on server {}".format(
                            auth_request.user_name, flags, request_id, self._client_data
                        ))

                    else:
                        self._logger.info("auth failed [{}] on server {}".format(request_id, self._client_data))
                        fail_auth()

            else:
                raise UnknownCommandError(command)

            # read next command
            command = (await self._reader.readline()).decode().rstrip("\n")


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
            # in any case, we can run the specific handler from here, the try-finally will clean up the connection
            elif first_command.split(" ")[0] in ("server", "reqauth", "confauth"):
                server_handler = ServerClientHandler(self._master_server, self._reader, self._writer)
                await server_handler.handle_server(first_command)

            else:
                raise UnknownCommandError(first_command)

        except CommandError as e:
            self._writer.write('error "{}"\n'.format(str(e)).encode("cube2"))
            self._logger.warning("\"%s\" error from client %r, closing connection", str(e), self._client_data)

        finally:
            self._writer.close()
            await self._writer.wait_closed()
