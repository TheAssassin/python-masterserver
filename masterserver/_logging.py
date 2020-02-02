import logging


def setup_logging(loglevel=logging.INFO, with_timestamps=False, force_colors=False, log_locations=False):
    fmt = "%(name)s[%(process)s] [%(levelname)s] %(message)s"

    if with_timestamps:
        fmt = "%(asctime)s " + fmt

    if log_locations:
        fmt = "%(pathname)s:%(lineno)d:\n" + fmt

    # basic logging setup
    try:
        import coloredlogs

    except ImportError:
        logging.basicConfig(format=fmt, level=loglevel)

    else:
        styles = coloredlogs.DEFAULT_FIELD_STYLES

        styles["pathname"] = {
            "color": "magenta",
        }
        styles["levelname"] = {
            "color": "cyan",
        }

        kwargs = dict(fmt=fmt, styles=styles)

        if force_colors:
            kwargs["isatty"] = True

        coloredlogs.install(loglevel, **kwargs)

    # set up logger
    logger = logging.getLogger("main")
    logger.setLevel(loglevel)


def get_logger(context: str = ""):
    logger_prefix = "masterserver"

    logger_name = logger_prefix

    if context:
        logger_name += "." + str(context)

    return logging.getLogger(logger_name)
