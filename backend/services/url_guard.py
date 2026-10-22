"""
Keeps ARIA's browser off internal networks (SSRF protection).

On Cloud Run, http://169.254.169.254 hands out access tokens for the service
account, and localhost exposes the backend itself: an agent steered by a
malicious page or prompt must not reach them.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from config import config

ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}

_dns_cache: dict[str, bool] = {}


def _ip_is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def _host_is_public(host: str) -> bool:
    host = host.strip("[]").lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith((".localhost", ".internal", ".local")):
        return False
    try:
        return _ip_is_public(host)  # literal IP
    except ValueError:
        pass
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return True  # unresolvable: let the browser fail with its own error
    public = all(_ip_is_public(info[4][0]) for info in infos)
    _dns_cache[host] = public
    return public


async def check_url(url: str) -> str | None:
    """Return a reason string if the URL must not be opened, else None."""
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        return f"scheme '{parts.scheme}' is not allowed"
    if not parts.hostname:
        return "URL has no host"
    if config.ALLOW_PRIVATE_NETWORK:
        return None
    if not await _host_is_public(parts.hostname):
        return f"host '{parts.hostname}' is on a private network"
    return None
