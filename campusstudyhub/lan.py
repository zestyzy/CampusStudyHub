"""Lightweight LAN notification helper using UDP broadcast/unicast."""
from __future__ import annotations

import socket
from typing import List, Tuple

from .models import LanTarget


def send_lan_notifications(message: str, targets: List[LanTarget]) -> List[Tuple[LanTarget, bool, str]]:
    """Send a short UTF-8 message to LAN targets via UDP.

    Returns a list of tuples (LanTarget, success, detail).
    """

    results: List[Tuple[LanTarget, bool, str]] = []
    if not targets:
        return results

    for target in targets:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(2.0)
                sock.sendto(message.encode("utf-8"), (target.host, target.port))
            results.append((target, True, "sent"))
        except OSError as exc:
            results.append((target, False, str(exc)))
    return results
