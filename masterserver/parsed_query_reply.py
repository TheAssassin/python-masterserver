import struct


class Cube2BytesStream:
    def __init__(self, data: bytes, offset: int):
        self.data = data
        self.offset = offset

    # see getint in src/shared/tools.cpp
    def next_int(self):
        next_int = struct.unpack(b"<b", self.data[self.offset:self.offset+1])[0]
        if next_int == -128:
            next_int = struct.unpack("<h", self.data[self.offset+1:self.offset+3])[0]
            self.offset += 3
        elif next_int == -127:
            next_int = struct.unpack("<i", self.data[self.offset+1:self.offset+5])[0]
            self.offset += 5
        else:
            self.offset += 1
        return next_int

    # see getstring in src/shared/tools.cpp
    def next_string(self):
        rv = []

        def getchar():
            return struct.unpack(b"<B", self.data[self.offset:self.offset+1])[0]

        char = getchar()

        while char != 0 and len(self.data) > 0:
            rv.append(bytes([char]))
            self.offset += 1
            char = getchar()

        self.offset += 1

        return b"".join(rv).decode("cube2")


class ParsedQueryReply:
    def __init__(self, query_reply: bytes):
        # integers inside queryreply data
        self.players_count = None
        self.number_of_ints = None
        self.protocol = None
        self.game_mode = None
        self.mutators = None
        self.time_remaining = None
        self.max_slots = None
        self.mastermode = None
        self.number_of_game_vars = None
        self.modification_percentage = None
        self.version = (None, None, None)
        self.version_platform = None
        self.version_arch = None
        self.game_state = None
        self.time_left = None

        # strings inside queryreply data
        self.map_name = None
        self.description = None
        self.versionbuild = None
        self.versionbranch = None

        # players are appended to the queryresponse and thus the last part
        self.players = None

        self._parse_query_reply(query_reply)

    def _parse_query_reply(self, query_reply: bytes):
        # Skip first 5 bytes as they are equal to the bytes sent as request
        stream = Cube2BytesStream(query_reply, 5)

        self.players_count = stream.next_int()

        # the number of integers following this value
        # after this, the map name string etc. will follow
        self.number_of_ints = stream.next_int()

        self.protocol = stream.next_int()
        self.game_mode = stream.next_int()

        self.mutators = stream.next_int()

        self.time_remaining = stream.next_int()
        self.max_slots = stream.next_int()
        self.mastermode = stream.next_int()
        self.modification_percentage = stream.next_int()
        self.number_of_game_vars = stream.next_int()
        self.version = (stream.next_int(),
                        stream.next_int(),
                        stream.next_int())
        self.version_platform = stream.next_int()
        self.version_arch = stream.next_int()
        self.game_state = stream.next_int()
        self.time_left = stream.next_int()

        # 15 values fetched
        # make sure there're no ints left to be fetched before interpreting
        # the following bytes as map name strings
        # TODO: notify in those cases so that the application is updated on
        # protocol updates
        for i in range(15, self.number_of_ints):
            # throw away value
            stream.next_int()

        self.map_name = stream.next_string()

        self.description = stream.next_string()

        if self.version[0] >= 1:
            # support for a "versionbuild" has been added in 1.6.0
            if self.version[1] >= 6:
                self.versionbuild = stream.next_string()

            # from 1.5.5 on, the server sends a versionbranch string which has to
            # be parsed
            if self.version[1] >= 5 and self.version[2] > 3:
                try:
                    self.versionbranch = stream.next_string()
                except struct.error:
                    # some servers send an invalid version branch string
                    # since it isn't used anywhere (yet), we'll just ignore
                    # the error
                    pass

        self.players = [stream.next_string() for i in range(self.players_count)]
        self.accounts = [stream.next_string().strip() for i in range(len(self.players))]

        # limit server description to 80 chars
        # https://github.com/red-eclipse/base/compare/0512024fef0f...01f6afe516d8
        self.description = self.description[:80]
