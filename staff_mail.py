"""Optional SMTP delivery for staff onboarding emails (credentials).

Configure with environment variables:
  STANCARE_SMTP_HOST     — e.g. smtp.gmail.com (required to send)
  STANCARE_SMTP_PORT     — default 587 (TLS). Use 465 for SMTP_SSL.
  STANCARE_SMTP_USER     — SMTP login if required
  STANCARE_SMTP_PASSWORD — SMTP password / app password
  STANCARE_SMTP_FROM     — From address (defaults to STANCARE_SMTP_USER)
  STANCARE_SMTP_USE_TLS  — default 1; set 0 for plain SMTP (not recommended)
"""

from __future__ import annotations

import os
import ssl
import smtplib
from email.message import EmailMessage


def send_staff_welcome_email(
    to_email: str,
    recipient_name: str,
    staff_id: int,
    temp_password: str,
    role: str,
) -> tuple[bool, str]:
    """Send staff ID and temporary password. Returns (ok, error_message)."""
    host = (os.environ.get("STANCARE_SMTP_HOST") or "").strip()
    if not host:
        return False, "SMTP is not configured (set STANCARE_SMTP_HOST)."

    port = int(os.environ.get("STANCARE_SMTP_PORT") or "587")
    user = (os.environ.get("STANCARE_SMTP_USER") or "").strip()
    password = os.environ.get("STANCARE_SMTP_PASSWORD") or ""
    from_addr = (os.environ.get("STANCARE_SMTP_FROM") or user).strip()
    if not from_addr:
        return False, "Set STANCARE_SMTP_FROM or STANCARE_SMTP_USER."

    use_tls = os.environ.get("STANCARE_SMTP_USE_TLS", "1").strip().lower() not in ("0", "false", "no")

    display_name = (recipient_name or "").strip() or "Colleague"
    body = f"""Hello {display_name},

Your StanCare staff account has been created.

Role: {role}
Staff ID (sign-in): {staff_id}
Temporary password: {temp_password}

Open StanCare, choose the sign-in tile that matches your role, then enter your Staff ID and temporary password.
You will be required to set a new password before using the system.

Please keep this email confidential and remove it after you have signed in.

— StanCare Hospital Management
"""

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = "StanCare — your staff account"
    msg["From"] = from_addr
    msg["To"] = to_email.strip()

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                if user:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if user:
                    server.login(user, password)
                server.send_message(msg)
    except Exception as e:
        return False, str(e)
    return True, ""
