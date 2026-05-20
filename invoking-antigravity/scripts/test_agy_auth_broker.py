"""Unit tests for scripts/agy_auth_broker.py pure helpers.

Covers OAuth-URL extraction and terminal-capability-query answering. The
pty/subprocess machinery in main() is not unit-tested — it requires a live
`agy` binary and a real OAuth TUI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agy_auth_broker as broker

_URL = (b"https://accounts.google.com/o/oauth2/auth?access_type=offline"
        b"&client_id=123.apps.googleusercontent.com&code_challenge=abc"
        b"&redirect_uri=https%3A%2F%2Fantigravity.google%2Foauth-callback"
        b"&response_type=code&scope=openid&state=xyz")


def test_extract_url_clean_buffer():
    assert broker.extract_oauth_url(b"prefix\n" + _URL + b"\nsuffix") == _URL


def test_extract_url_none_when_absent():
    assert broker.extract_oauth_url(b"no url here, just text") is None
    assert broker.extract_oauth_url(b"") is None


def test_extract_url_amid_escape_codes():
    # the TUI wraps the URL in cursor-positioning escape sequences
    noisy = b"\x1b[2J\x1b[1;1H" + _URL + b"\x1b[0m\x1b[2;1H"
    assert broker.extract_oauth_url(noisy) == _URL


def test_extract_url_stops_at_whitespace():
    assert broker.extract_oauth_url(_URL + b" trailing words") == _URL


def test_extract_url_ignores_non_oauth_google_urls():
    assert broker.extract_oauth_url(b"see https://accounts.google.com/signin") is None


def test_capability_reply_decrqm_2026():
    assert broker.capability_replies(b"\x1b[?2026$p") == b"\x1b[?2026;2$y"


def test_capability_reply_primary_da():
    assert broker.capability_replies(b"\x1b[c") == b"\x1b[?62;1;6c"


def test_capability_reply_cursor_position_request():
    assert broker.capability_replies(b"\x1b[6n") == b"\x1b[1;1R"


def test_capability_reply_empty_for_plain_output():
    assert broker.capability_replies(b"just normal TUI text, no queries") == b""


def test_capability_reply_concatenates_multiple_queries():
    out = broker.capability_replies(b"\x1b[?2026$p\x1b[?2027$p\x1b[6n")
    assert b"\x1b[?2026;2$y" in out
    assert b"\x1b[?2027;2$y" in out
    assert b"\x1b[1;1R" in out


if __name__ == "__main__":
    fns = sorted(n for n in dir() if n.startswith("test_"))
    for n in fns:
        globals()[n]()
        print(f"  ok  {n}")
    print(f"{len(fns)} passed")
