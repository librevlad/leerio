"""Email sending via Resend API. Falls back to console logging in dev."""

import logging
import os

import httpx

logger = logging.getLogger("leerio.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = "Leerio <noreply@leerio.app>"


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send plain-text email. Returns True on success."""
    if not RESEND_API_KEY:
        logger.info("[DEV] Email to %s: %s — %s", to, subject, body)
        return True
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": FROM_EMAIL,
                    "to": [to],
                    "subject": subject,
                    "text": body,
                },
            )
            if res.status_code >= 400:
                logger.error("Resend error %s: %s", res.status_code, res.text[:200])
                return False
            return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


async def send_verification_code(to: str, code: str) -> bool:
    """Send email verification code."""
    return await send_email(
        to,
        "Код подтверждения Leerio",
        f"Ваш код подтверждения: {code}\n\nДействителен 15 минут.\n\nЕсли вы не запрашивали этот код, проигнорируйте это письмо.",
    )


async def send_reset_code(to: str, code: str) -> bool:
    """Send password reset code."""
    return await send_email(
        to,
        "Сброс пароля Leerio",
        f"Код для сброса пароля: {code}\n\nДействителен 15 минут.\n\nЕсли вы не запрашивали сброс пароля, проигнорируйте это письмо.",
    )
