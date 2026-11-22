"""WhatsApp Cloud API (Meta) sender.

Credentials are read from the environment / .env through Settings:
WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, and optionally
WHATSAPP_API_VERSION and WHATSAPP_DEFAULT_COUNTRY_CODE.

The access token is a secret: it is never stored in the database, never
returned to the UI and never written to logs or exception messages.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com"

# (url, headers, payload) -> parsed JSON response
Transport = Callable[[str, Dict[str, str], Dict], Dict]


class WhatsAppError(Exception):
    """A message could not be sent; the text is safe to show to the user."""


class WhatsAppNotConfigured(WhatsAppError):
    """Credentials are missing, so no request was attempted."""


def _post_json(url: str, headers: Dict[str, str], payload: Dict,
               timeout: int = 15) -> Dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = (body.get("error") or {}).get("message") or ""
        except Exception:
            detail = ""
        message = f"WhatsApp rejected the message ({exc.code})"
        raise WhatsAppError(f"{message}: {detail}" if detail else f"{message}.") from None
    except urllib.error.URLError as exc:
        raise WhatsAppError(f"Cannot reach WhatsApp: {exc.reason}") from None


class WhatsAppService:
    """Send plain-text WhatsApp messages through the Meta Cloud API."""

    @staticmethod
    def _credentials():
        token = (settings.whatsapp_access_token or "").strip()
        phone_number_id = (settings.whatsapp_phone_number_id or "").strip()
        return token, phone_number_id

    @classmethod
    def configuration_error(cls) -> Optional[str]:
        """
        Returns a user-facing explanation of what is missing, or None.
        Names the environment variables — never their values.
        """
        token, phone_number_id = cls._credentials()
        missing = []
        if not token:
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not phone_number_id:
            missing.append("WHATSAPP_PHONE_NUMBER_ID")
        if not missing:
            return None
        return (
            "WhatsApp is not configured. Set "
            + " and ".join(missing)
            + " in the environment or a .env file, then restart the application."
        )

    @classmethod
    def is_configured(cls) -> bool:
        return cls.configuration_error() is None

    @staticmethod
    def normalize_phone(number: str) -> str:
        """
        Converts a locally typed number to the digits-only international
        form the Cloud API requires. '06 12 34 56 78' becomes
        '212612345678' with the default country code 212 (Morocco).
        """
        digits = "".join(ch for ch in (number or "") if ch.isdigit())
        if not digits:
            return ""
        if (number or "").strip().startswith("00"):
            digits = digits[2:]

        default_code = (settings.whatsapp_default_country_code or "").strip()
        if not default_code:
            return digits
        if digits.startswith("0"):
            return default_code + digits[1:]
        if len(digits) == 9 and not digits.startswith(default_code):
            return default_code + digits
        return digits

    @classmethod
    def send_text(cls, to: str, body: str,
                  transport: Optional[Transport] = None) -> Dict:
        """
        Sends one plain-text message. Raises WhatsAppNotConfigured before
        any network call when credentials are absent, so the UI can show
        setup instructions instead of a request failure.
        """
        error = cls.configuration_error()
        if error:
            raise WhatsAppNotConfigured(error)

        text = (body or "").strip()
        if not text:
            raise ValueError("The WhatsApp message cannot be empty.")

        number = cls.normalize_phone(to)
        if not number:
            raise ValueError("A recipient phone number is required.")

        token, phone_number_id = cls._credentials()
        version = (settings.whatsapp_api_version or "v20.0").strip()
        if not re.fullmatch(r"v\d+\.\d+", version):
            version = "v20.0"

        url = f"{GRAPH_BASE}/{version}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        sender = transport or _post_json
        try:
            response = sender(url, headers, payload)
        except WhatsAppError:
            raise
        except Exception as exc:
            # Never echo the request (and its Authorization header) here.
            raise WhatsAppError(f"WhatsApp request failed: {exc}") from None

        message_id = ""
        try:
            message_id = response["messages"][0]["id"]
        except (KeyError, IndexError, TypeError):
            pass
        logger.info("WhatsApp message accepted (id=%s).", message_id or "unknown")
        return response or {}

    @staticmethod
    def build_statement_message(statement: Dict) -> str:
        """Prefills the composer with the statement summary in French."""
        party = statement.get("party") or {}
        name = party.get("name") or "Client"
        is_customer = statement.get("kind") == "customer"
        kind_label = "client" if is_customer else "fournisseur"

        start = statement.get("date_from")
        end = statement.get("date_to")
        if start and end:
            period = f"du {start:%d/%m/%Y} au {end:%d/%m/%Y}"
        else:
            period = "à ce jour"

        closing = statement.get("closing_balance") or 0
        if is_customer:
            if closing >= 0:
                balance_line = f"Solde à régler : {closing:,.2f} DH"
            else:
                balance_line = f"Crédit en votre faveur : {abs(closing):,.2f} DH"
        else:
            balance_line = f"Solde : {closing:,.2f} DH"

        return (
            f"Bonjour {name},\n\n"
            f"Voici votre relevé de compte {kind_label} {period} :\n"
            f"- Solde d'ouverture : {statement.get('opening_balance', 0):,.2f} DH\n"
            f"- Total débit : {statement.get('total_debit', 0):,.2f} DH\n"
            f"- Total crédit : {statement.get('total_credit', 0):,.2f} DH\n"
            f"- {balance_line}\n\n"
            "Cordialement,\nTAJ FROID"
        )
