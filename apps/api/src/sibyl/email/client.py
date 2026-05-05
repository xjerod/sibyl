"""Resend email client wrapper."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sibyl.email.templates import EmailTemplate

log = structlog.get_logger()

_client: EmailClient | None = None


class EmailClient:
    """Wrapper around Resend for sending transactional emails."""

    def __init__(self) -> None:
        from sibyl.config import settings

        self._api_key = settings.resend_api_key.get_secret_value()
        self._from_address = settings.email_from
        self._outbox_path = settings.email_outbox_path.strip()
        self._resend: object | None = None

        if self._api_key:
            try:
                import resend

                resend.api_key = self._api_key
                self._resend = resend
            except ImportError:
                log.warning("resend package not installed, emails will be logged only")

    @property
    def configured(self) -> bool:
        """Check if email sending is configured."""
        return bool(self._api_key and self._resend)

    async def send(
        self,
        *,
        to: str | list[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
    ) -> str | None:
        """Send an email.

        Returns:
            Email ID if sent successfully, None if not configured.
        """
        recipients = [to] if isinstance(to, str) else to

        self._write_outbox(
            to=recipients,
            subject=subject,
            html=html,
            text=text,
            reply_to=reply_to,
        )

        if not self.configured:
            log.info(
                "email_skipped",
                reason="not_configured",
                to=recipients,
                subject=subject,
            )
            return None

        try:
            import resend

            params: dict[str, object] = {
                "from_": self._from_address,
                "to": recipients,
                "subject": subject,
                "html": html,
            }
            if text:
                params["text"] = text
            if reply_to:
                params["reply_to"] = reply_to

            result = resend.Emails.send(params)
            email_id = result.get("id") if isinstance(result, dict) else None

            log.info("email_sent", email_id=email_id, to=recipients, subject=subject)
            return email_id

        except Exception:
            log.exception("email_failed", to=recipients, subject=subject)
            return None

    def _write_outbox(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        text: str | None,
        reply_to: str | None,
    ) -> None:
        if not self._outbox_path:
            return
        path = Path(self._outbox_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "created_at": datetime.now(UTC).isoformat(),
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "reply_to": reply_to,
            }
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, sort_keys=True))
                file.write("\n")
        except Exception:
            log.exception("email_outbox_write_failed", path=str(path))

    async def send_template(
        self,
        template: EmailTemplate,
        *,
        to: str | list[str],
        reply_to: str | None = None,
    ) -> str | None:
        """Send an email using a template."""
        return await self.send(
            to=to,
            subject=template.subject,
            html=template.render_html(),
            text=template.render_text(),
            reply_to=reply_to,
        )


def get_email_client() -> EmailClient:
    """Get or create the global email client singleton."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = EmailClient()
    return _client
