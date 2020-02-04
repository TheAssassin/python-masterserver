import pytest

from masterserver import MasterServer


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
