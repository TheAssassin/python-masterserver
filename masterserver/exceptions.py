class CommandError(Exception):
    def __init__(self, command: str):
        super().__init__()
        self.command = command

    def __str__(self):
        raise NotImplementedError()

    def __repr__(self):
        return "<{}({})>".format(self.__class__.__name__, self.command)


class UnknownCommandError(CommandError):
    def __str__(self):
        return "Unknown command: %s" % self.command


class InvalidCommandError(CommandError):
    def __str__(self):
        return "Invalid command: %s" % self.command
