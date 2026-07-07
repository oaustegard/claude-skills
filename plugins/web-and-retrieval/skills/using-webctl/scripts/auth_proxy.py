"""
Local proxy that injects Proxy-Authorization header for authenticated proxies.

Solves: Chromium fails HTTPS CONNECT tunnels through proxies requiring auth,
even when credentials are provided via Playwright's proxy config.

Usage: Import get_local_proxy_url() and pass result to Playwright's proxy config.
"""

import asyncio
import base64
import os
import socket
import threading
from urllib.parse import urlparse

_proxy_server = None
_proxy_thread = None
_local_port = 18080


def get_local_proxy_url():
    """
    Get URL for the local auth-injecting proxy.
    
    Returns:
        str: Local proxy URL if upstream requires auth, else upstream URL directly.
        None: If no proxy configured.
    """
    proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    if not proxy_url:
        return None
    
    parsed = urlparse(proxy_url)
    if not parsed.username:
        # No auth needed, use upstream directly
        return proxy_url
    
    # Auth required - start local proxy
    start_auth_proxy()
    return f"http://127.0.0.1:{_local_port}"


def start_auth_proxy():
    """Start the local auth-injecting proxy if not already running."""
    global _proxy_server, _proxy_thread
    
    if _proxy_server is not None:
        return  # Already running
    
    proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    parsed = urlparse(proxy_url)
    
    credentials = f"{parsed.username}:{parsed.password}"
    auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
    upstream_host = parsed.hostname
    upstream_port = parsed.port
    
    def handle_client(client_sock):
        """Handle a single client connection with auth injection."""
        proxy_sock = None
        try:
            # Read request until headers complete
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    return
                data += chunk
            
            # Connect to upstream proxy
            proxy_sock = socket.socket()
            proxy_sock.settimeout(30)
            proxy_sock.connect((upstream_host, upstream_port))
            
            # Inject Proxy-Authorization if missing
            if b"Proxy-Authorization:" not in data:
                parts = data.split(b"\r\n\r\n", 1)
                headers = parts[0] + f"\r\nProxy-Authorization: {auth_header}".encode()
                data = headers + b"\r\n\r\n"
                if len(parts) > 1:
                    data += parts[1]
            
            # Forward to upstream
            proxy_sock.send(data)
            
            # Read response headers
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = proxy_sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            
            # Send response to client
            client_sock.send(response)
            
            # If CONNECT succeeded (200), establish bidirectional tunnel
            status_line = response.split(b"\r\n")[0]
            if b"200" in status_line:
                def forward(src, dst):
                    try:
                        while True:
                            d = src.recv(4096)
                            if not d:
                                break
                            dst.send(d)
                    except Exception:
                        pass
                
                t1 = threading.Thread(target=forward, args=(client_sock, proxy_sock), daemon=True)
                t2 = threading.Thread(target=forward, args=(proxy_sock, client_sock), daemon=True)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
                
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            try:
                if proxy_sock:
                    proxy_sock.close()
            except Exception:
                pass
    
    def serve():
        """Accept and dispatch client connections."""
        global _proxy_server
        _proxy_server = socket.socket()
        _proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _proxy_server.bind(("127.0.0.1", _local_port))
        _proxy_server.listen(10)
        while True:
            try:
                client, _ = _proxy_server.accept()
                threading.Thread(target=handle_client, args=(client,), daemon=True).start()
            except Exception:
                break
    
    _proxy_thread = threading.Thread(target=serve, daemon=True)
    _proxy_thread.start()


def stop_auth_proxy():
    """Stop the local auth proxy."""
    global _proxy_server, _proxy_thread
    if _proxy_server:
        try:
            _proxy_server.close()
        except Exception:
            pass
        _proxy_server = None
        _proxy_thread = None
