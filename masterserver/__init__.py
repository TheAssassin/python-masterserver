# first we need to import the logging module
from ._logging import get_logger, setup_logging  # noqa: F401

# then we make sure the codec is available
from ._codec import register_codec
register_codec()


# now the regular imports may follow
from .masterserver import MasterServer  # noqa: F401 E402

__all__ = (MasterServer,)
