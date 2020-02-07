from masterserver.red_eclipse_server import RedEclipseServer


def test_eq():
    srv1 = RedEclipseServer("123.4.5.6", 12345, 123, "", "", "", "")
    srv2 = RedEclipseServer("123.4.5.7", 12345, 123, "", "", "", "")

    assert srv1 == srv1
    assert srv2 == srv2

    assert srv1 != srv2
    assert srv2 != srv1

    # test whether servers with equal IP/port are recognized as the same
    srv3 = RedEclipseServer("123.4.5.6", 12345, 456, "", "", "", "")
    assert srv1 == srv3
    assert srv3 == srv1


def test_hash():
    srv1 = RedEclipseServer("123.4.5.6", 12345, 123, "", "", "", "")
    srv2 = RedEclipseServer("123.4.5.7", 12345, 123, "", "", "", "")

    assert hash(srv2) == hash(srv2)
    assert hash(srv1) == hash(srv1)

    assert hash(srv1) != hash(srv2)

    s = set()

    for i in range(100):
        s.add(srv1)
        s.add(srv2)

    assert len(s) == 2

    # test whether servers with equal IP/port are recognized as the same
    srv3 = RedEclipseServer("123.4.5.6", 12345, 456, "", "", "", "")
    for i in range(100):
        s.add(srv3)

    assert len(s) == 2
    assert srv1 in s
    assert srv3 in s

    # make sure set.add() doesn't replace the existing object
    srv1_from_s = list(filter(lambda x: x == srv1, s))[0]
    assert srv1_from_s.priority == srv1.priority
    assert srv1_from_s.priority != srv3.priority
