"""Zero-network default.

``offline()`` blocks outbound socket connections and DNS resolution in-process. With
``allow_localhost=True`` only loopback endpoints are allowed (for localhost mocks).
Every blocked attempt is recorded so a run can prove it made zero remote calls.

This is a defense-in-depth guard for the PBD process; it is not an OS sandbox and does
not control subprocesses. PBD itself never spawns network tools in this round.
"""

from __future__ import annotations

import contextlib
import ipaddress
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


class NetworkBlocked(ConnectionError):
    """Raised when code attempts a non-authorized network operation."""


@dataclass
class NetworkLedger:
    blocked: list[str] = field(default_factory=list)
    allowed_local: list[str] = field(default_factory=list)


_LOCK = threading.RLock()
_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}


def _is_loopback(host: Any) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _host_of(address: Any) -> Any:
    if isinstance(address, tuple) and address:
        return address[0]
    return address  # AF_UNIX paths etc.


@contextlib.contextmanager
def offline(allow_localhost: bool = False) -> Iterator[NetworkLedger]:
    ledger = NetworkLedger()
    with _LOCK:
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_getaddrinfo = socket.getaddrinfo
        orig_create_connection = socket.create_connection

        def check(address: Any) -> None:
            host = _host_of(address)
            if allow_localhost and _is_loopback(host):
                ledger.allowed_local.append(str(host))
                return
            ledger.blocked.append(str(host))
            raise NetworkBlocked(f"network access blocked by PBD offline mode: {host!r}")

        def guarded_connect(self: socket.socket, address: Any) -> None:
            if self.family in (socket.AF_INET, socket.AF_INET6):
                check(address)
            orig_connect(self, address)

        def guarded_connect_ex(self: socket.socket, address: Any) -> int:
            if self.family in (socket.AF_INET, socket.AF_INET6):
                check(address)
            return orig_connect_ex(self, address)

        def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
            if host is not None:
                check((host,))
            return orig_getaddrinfo(host, *args, **kwargs)

        def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
            check(address)
            return orig_create_connection(address, *args, **kwargs)

        socket.socket.connect = guarded_connect  # type: ignore[method-assign,assignment]
        socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign,assignment]
        socket.getaddrinfo = guarded_getaddrinfo
        socket.create_connection = guarded_create_connection
        try:
            yield ledger
        finally:
            socket.socket.connect = orig_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
            socket.getaddrinfo = orig_getaddrinfo
            socket.create_connection = orig_create_connection
