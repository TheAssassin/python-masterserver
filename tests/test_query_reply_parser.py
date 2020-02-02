import pytest

from masterserver.parsed_query_reply import ParsedQueryReply


# TODO: add more test data
@pytest.mark.parametrize("input,data", [
    (
        b'\x81\xec\x04\x01\x00\x00\x0f\x80\xe6\x00\x03\x00\x80X\x02 \x00\x80\x86\x13\x05\x01\x06\x00\x02@\x00\x00'
        b'dropzone\x00Einherjer Europe [linuxiuvat.de]\x00\x00',
        {
            "description": "Einherjer Europe [linuxiuvat.de]",
            "map_name": "dropzone",
            "players_count": 0,
            "players": list(),
            "accounts": list(),
        }
    ),
])
def test_parsed_query_reply(input, data: dict):
    parsed = ParsedQueryReply(input)

    for k, v in data.items():
        assert getattr(parsed, k) == v
