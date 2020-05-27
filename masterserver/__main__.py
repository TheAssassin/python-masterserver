import asyncio
import json
import logging
import os
import sys

from masterserver import MasterServer, setup_logging

from aiohttp import web


# try to set up Sentry if the SDK is installed and a sentry DSN is available from the environment
try:
    import sentry_sdk
except ImportError:
    print("Sentry SDK not found, Sentry integration not available")
else:
    try:
        sentry_sdk.init(os.environ["SENTRY_DSN"])
    except KeyError:
        pass
    else:
        print("Set up Sentry integration successfully")


if "DEBUG" in os.environ:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO

setup_logging(force_colors=True, loglevel=loglevel)


if len(sys.argv) > 1:
    ms = MasterServer(backup_file=sys.argv[1])
else:
    ms = MasterServer()


async def handle(request):
    data = {
        "servers": [
            i.to_json_dict() for i in ms.servers
        ]
    }

    text = json.dumps(data, indent=4)

    return web.Response(text=text, content_type="application/json")


app = web.Application()
app.add_routes([web.get("/", handle)])

for server in os.environ.get("PROXIED_SERVERS", "").split(","):
    if not server:
        continue

    ms.add_server_to_proxy(server, 28800)


if __name__ == "__main__":
    # first we start the masterserver
    asyncio.get_event_loop().run_until_complete(ms.start_server())

    # then we run the web app, which will internally run the asyncio event loop and therefore also run the masterserver
    web.run_app(app, port=28799)
