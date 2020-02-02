import pytest

from masterserver._codec import register_codec, Cube2Codec


register_codec()


@pytest.mark.parametrize("test_string,expected_result", [
    ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("äöüÄÖÜ", b"\x86\x96\x9c\x05\x1b\x7f"),
])
def test_cube2_encode(test_string, expected_result):
    assert test_string.encode("cube2") == expected_result


@pytest.mark.parametrize("test_bytes,expected_result", [
    (b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (b"\x86\x96\x9c\x05\x1b\x7f", "äöüÄÖÜ"),
])
def test_cube2_decode(test_bytes, expected_result):
    assert test_bytes.decode("cube2") == expected_result


@pytest.mark.parametrize("test_string", [
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "äöüÄÖÜ",
])
def test_cube2_encode_decode(test_string):
    assert test_string == test_string.encode("cube2").decode("cube2")
