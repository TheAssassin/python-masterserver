import asyncio
import json
import os
import sys

from masterserver import MasterServer, setup_logging

from aiohttp import web


setup_logging(force_colors=True)


if len(sys.argv) > 1:
    ms = MasterServer(database=sys.argv[1])
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
