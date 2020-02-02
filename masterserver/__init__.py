# first we need to import the logging module
from ._logging import get_logger, setup_logging

# then we make sure the codec is available
from ._codec import register_codec  # noqa
register_codec()


# now the regular imports may follow
from .masterserver import MasterServer  # noqa

__all__ = (MasterServer,)
