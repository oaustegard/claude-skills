#!/usr/bin/env python3
"""Headless OAuth broker for the Antigravity CLI (`agy`).

`agy -p` (print mode) gives the OAuth prompt only 30 s — too short for a
human-in-the-loop login. `agy -i` (interactive TUI) has no auth timeout but
must be driven through a pseudo-terminal. This broker spawns `agy -i` under
a pty, answers the terminal capability queries so the TUI renders,
auto-selects "Google OAuth", scrapes the auth URL, and feeds back an
authorization code.

It also exports fake SSH env vars so `agy` uses file-based token storage
(`~/.gemini/antigravity-cli/antigravity-oauth-token`) instead of the OS
keyring — the container has no D-Bus, so the keyring path fails silently.

Usage:
    python3 agy_auth_broker.py &              # launch; spawns agy, captures URL
    cat /tmp/agybroker/url                    # -> give this URL to a human
    # human consents in a browser, copies the authorization code
    printf '<code>' > /tmp/agybroker/code     # broker feeds it to agy

After a successful auth `agy` writes the token file itself; subsequent
`agy -p` calls (with the same SSH env set) run non-interactively.

State directory (default /tmp/agybroker): url, code, status, log.
The whole flow must finish before the CCotw container idle-pauses (a few
minutes) — a paused container kills the live `agy` process.
"""
import os, pty, time, select, re, fcntl, termios, struct, sys

OAUTH_URL_RE = re.compile(rb"https://accounts\.google\.com/o/oauth2/auth[^\s\x1b\"']+")


def extract_oauth_url(buf):
    """Return the Google OAuth URL found in a pty output buffer, or None.

    The match deliberately stops at whitespace, ESC (0x1b) and quotes, so a
    URL surrounded by TUI escape sequences is still recovered intact."""
    m = OAUTH_URL_RE.search(buf)
    return m.group(0) if m else None


def capability_replies(data):
    """Bytes to write back so a TUI's terminal capability queries are
    answered and it stops waiting. Returns b'' when `data` has no queries."""
    out = b""
    for mode_n in (2026, 2027, 1016, 1049):
        if (b"\x1b[?%d$p" % mode_n) in data:
            out += b"\x1b[?%d;2$y" % mode_n
    if b"\x1b[c" in data or b"\x1b[>c" in data or b"\x1b[>0c" in data:
        out += b"\x1b[?62;1;6c"
    if b"\x1b[6n" in data:
        out += b"\x1b[1;1R"
    return out


def main():
    state_dir = os.environ.get("AGY_BROKER_DIR", "/tmp/agybroker")
    os.makedirs(state_dir, exist_ok=True)
    log_p, url_p, code_p, status_p = (
        f"{state_dir}/{n}" for n in ("log", "url", "code", "status"))
    for f in (log_p, url_p, code_p, status_p):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass

    prompt = sys.argv[1] if len(sys.argv) > 1 else "reply with the single word OK"
    agy = os.path.expanduser("~/.local/bin/agy")

    def status(s):
        open(status_p, "w").write(s + "\n")

    status("starting")
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["PATH"] = os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")
        # SSH env => agy uses file-based token storage, not the D-Bus keyring
        os.environ.setdefault("SSH_CONNECTION", "203.0.113.1 50000 203.0.113.2 22")
        os.environ.setdefault("SSH_CLIENT", "203.0.113.1 50000 22")
        os.environ.setdefault("SSH_TTY", "/dev/pts/0")
        os.execv(agy, [agy, "-i", prompt])
        os._exit(1)

    # wide pty so a ~400-char URL is never line-wrapped
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 1000, 0, 0))

    buf = b""
    log = open(log_p, "wb")
    url_done = code_sent = menu_done = False
    start = time.time()
    status("running")
    while True:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                data = os.read(fd, 8192)
            except OSError:
                data = b""
            if not data:
                break
            buf += data
            log.write(data)
            log.flush()
            reply = capability_replies(data)
            if reply:
                os.write(fd, reply)
            # menu: "Google OAuth" is option 1, already highlighted -> Enter
            if not menu_done and b"Select login method" in buf:
                time.sleep(0.4)
                os.write(fd, b"\r")
                menu_done = True
                status("oauth-selected")
            if not url_done:
                url = extract_oauth_url(buf)
                if url:
                    open(url_p, "wb").write(url)
                    url_done = True
                    status("url-ready")
        if not code_sent and os.path.exists(code_p):
            code = open(code_p).read().strip()
            if code:
                os.write(fd, code.encode() + b"\r")
                code_sent = True
                status("code-sent")
        if time.time() - start > 1200:
            break
    status("exited")


if __name__ == "__main__":
    main()
