class CommandError(Exception):
    def __init__(self, command: str):
        self.command = command

    def __str__(self):
        return "Invalid command {}".format(self.command)

    def __repr__(self):
        return "<{}({})>".format(self.__class__.__name__, str(self))


class UnknownCommandError(CommandError):
    pass


class InvalidCommandError(CommandError):
    pass
