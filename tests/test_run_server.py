import asyncio
import os

import pytest

from masterserver import MasterServer, setup_logging


@pytest.fixture(scope="session", autouse=True)
def enable_logs():
    setup_logging()


@pytest.fixture(scope="function", autouse=True)
def masterserver(unused_tcp_port):
    ms = MasterServer(port=unused_tcp_port)
    return ms


@pytest.mark.asyncio
async def test_start_and_stop(masterserver):
    await masterserver.start_server()
    await masterserver.stop_server()


@pytest.mark.asyncio
async def test_start_twice(masterserver):
    await masterserver.start_server()

    try:
        with pytest.raises(RuntimeError):
            await masterserver.start_server()

    finally:
        await masterserver.stop_server()


@pytest.mark.asyncio
async def test_stop_twice(masterserver):
    await masterserver.start_server()
    await masterserver.stop_server()

    with pytest.raises(RuntimeError):
        await masterserver.stop_server()


@pytest.mark.asyncio
async def test_stop_before_start(masterserver):
    with pytest.raises(RuntimeError):
        await masterserver.stop_server()


@pytest.mark.asyncio
async def test_update_command_empty_server(masterserver):
    await masterserver.start_server()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", masterserver.port)

        try:
            writer.write(b"update\n")

            recv_data = await asyncio.wait_for(reader.read(), timeout=5.0)

            assert recv_data == b'setversion 160 230\nclearservers\n'

        finally:
            writer.close()

    finally:
        await masterserver.stop_server()
