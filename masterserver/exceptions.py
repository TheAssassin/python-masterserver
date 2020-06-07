class CommandError(Exception):
    def __init__(self, command: str):
        self.command = command

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "<{}({})>".format(self.__class__.__name__, self.command)


class UnknownCommandError(CommandError):
    pass


class InvalidCommandError(CommandError):
    pass
