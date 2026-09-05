"""Shared fakes for network-free feed tests.

Spec ARCH-21: the suite never hits the network. These helpers replace
urllib.request.urlopen with callables that record requested URLs and return
canned bodies.
"""
import json as jsonlib
import urllib.request


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def json_body(payload) -> bytes:
    return jsonlib.dumps(payload).encode()


def urlopen_returning(body_for):
    """Replace urllib.request.urlopen with a callable body_for(url) -> bytes."""

    def fake(req, timeout=None):
        url = req.full_url if isinstance(req, urllib.request.Request) else req
        return FakeResponse(body_for(url))

    return fake


def urlopen_raising(exc):
    def fake(req, timeout=None):
        raise exc

    return fake
