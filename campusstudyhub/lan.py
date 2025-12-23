"""Lightweight LAN/email notification helper using UDP and SMTP."""
from __future__ import annotations

import socket
import smtplib
from email.message import EmailMessage
from typing import List, Tuple

from .models import LanTarget


def send_lan_notifications(
    message: str,
    targets: List[LanTarget],
    smtp_host: str = "localhost",
    smtp_port: int = 25,
    smtp_sender: str | None = None,
) -> List[Tuple[LanTarget, bool, str]]:
    """Send a short UTF-8 message via UDP and optionally email.

    Returns a list of tuples (LanTarget, success, detail) describing the last
    attempted channel. If both UDP and email are configured, success reflects
    the AND result; details aggregate failures.
    """

    results: List[Tuple[LanTarget, bool, str]] = []
    if not targets:
        return results

    for target in targets:
        errors: List[str] = []
        udp_ok = True
        if target.port:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(2.0)
                    sock.sendto(message.encode("utf-8"), (target.host, int(target.port)))
            except OSError as exc:
                udp_ok = False
                errors.append(f"udp:{exc}")

        mail_ok = True
        if target.email:
            if not smtp_sender:
                mail_ok = False
                errors.append("email:missing sender")
            else:
                try:
                    msg = EmailMessage()
                    msg["From"] = smtp_sender
                    msg["To"] = target.email
                    msg["Subject"] = "CampusStudyHub 通知"
                    msg.set_content(message)
                    with smtplib.SMTP(host=smtp_host, port=smtp_port, timeout=8) as server:
                        server.send_message(msg)
                except Exception as exc:  # pragma: no cover - best effort
                    mail_ok = False
                    errors.append(f"email:{exc}")

        if not target.port and not target.email:
            errors.append("no channel configured")
            udp_ok = False
            mail_ok = False

        success = udp_ok and mail_ok
        detail = "ok" if success else ";".join(errors) or "unknown"
        results.append((target, success, detail))
    return results
