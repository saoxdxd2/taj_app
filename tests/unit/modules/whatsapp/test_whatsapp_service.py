"""WhatsApp Cloud API sender: configuration, request shape, phone formats."""
import io
import urllib.error
from datetime import datetime
from decimal import Decimal

import pytest

from src.core.config import settings
from src.modules.whatsapp.services import (
    WhatsAppError, WhatsAppNotConfigured, WhatsAppService, _post_json,
)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "test-token-123")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "whatsapp_api_version", "v20.0")
    monkeypatch.setattr(settings, "whatsapp_default_country_code", "212")


@pytest.fixture
def unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", None)
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", None)


def test_configuration_error_names_the_missing_variables_without_values(
    monkeypatch,
):
    monkeypatch.setattr(settings, "whatsapp_access_token", None)
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123")

    error = WhatsAppService.configuration_error()

    assert "WHATSAPP_ACCESS_TOKEN" in error
    assert "WHATSAPP_PHONE_NUMBER_ID" not in error
    assert WhatsAppService.is_configured() is False


def test_unconfigured_send_never_calls_the_network(unconfigured):
    called = []

    def transport(url, headers, payload):
        called.append(url)
        return {}

    with pytest.raises(WhatsAppNotConfigured, match="WHATSAPP_ACCESS_TOKEN"):
        WhatsAppService.send_text("0612345678", "Bonjour", transport=transport)

    assert called == []


def test_send_text_builds_a_cloud_api_request(configured):
    calls = {}

    def transport(url, headers, payload):
        calls["url"] = url
        calls["headers"] = headers
        calls["payload"] = payload
        return {"messages": [{"id": "wamid.TEST"}]}

    response = WhatsAppService.send_text(
        "06 12 34 56 78", "Bonjour", transport=transport
    )

    assert calls["url"] == "https://graph.facebook.com/v20.0/1234567890/messages"
    assert calls["headers"]["Authorization"] == "Bearer test-token-123"
    assert calls["payload"]["messaging_product"] == "whatsapp"
    assert calls["payload"]["to"] == "212612345678"
    assert calls["payload"]["type"] == "text"
    assert calls["payload"]["text"]["body"] == "Bonjour"
    assert response["messages"][0]["id"] == "wamid.TEST"


@pytest.mark.parametrize("raw,expected", [
    ("0612345678", "212612345678"),
    ("06 12 34 56 78", "212612345678"),
    ("+212 612 345 678", "212612345678"),
    ("00212612345678", "212612345678"),
    ("612345678", "212612345678"),
    ("", ""),
])
def test_phone_numbers_are_normalised_to_international_digits(raw, expected):
    assert WhatsAppService.normalize_phone(raw) == expected


def test_empty_message_and_recipient_are_rejected(configured):
    with pytest.raises(ValueError, match="cannot be empty"):
        WhatsAppService.send_text("0612345678", "   ", transport=lambda *a: {})
    with pytest.raises(ValueError, match="phone number"):
        WhatsAppService.send_text("", "Bonjour", transport=lambda *a: {})


def test_transport_failure_never_reveals_the_access_token(configured):
    def transport(url, headers, payload):
        raise RuntimeError("connection reset")

    with pytest.raises(WhatsAppError) as info:
        WhatsAppService.send_text("0612345678", "Bonjour", transport=transport)

    assert "connection reset" in str(info.value)
    assert "test-token-123" not in str(info.value)


def test_api_error_message_is_surfaced_without_the_token(configured, monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"Invalid OAuth access token."}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(WhatsAppError) as info:
        WhatsAppService.send_text("0612345678", "Bonjour")

    message = str(info.value)
    assert "401" in message
    assert "Invalid OAuth access token." in message
    assert "test-token-123" not in message


def test_http_error_without_a_json_body_still_gives_a_clear_message(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 500, "Server Error", {}, io.BytesIO(b"oops")
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(WhatsAppError, match="rejected the message \\(500\\)"):
        _post_json("https://graph.facebook.com/test", {}, {})


def test_statement_message_summarises_a_customer_balance():
    statement = {
        "kind": "customer",
        "party": {"name": "Froid Atlas SARL"},
        "date_from": datetime(2026, 10, 22),
        "date_to": datetime(2026, 11, 22),
        "opening_balance": Decimal("0.00"),
        "total_debit": Decimal("6000.00"),
        "total_credit": Decimal("3500.00"),
        "closing_balance": Decimal("2500.00"),
    }

    text = WhatsAppService.build_statement_message(statement)

    assert "Bonjour Froid Atlas SARL" in text
    assert "22/10/2026" in text and "22/11/2026" in text
    assert "Solde à régler : 2,500.00 DH" in text
    assert "Total débit : 6,000.00 DH" in text


def test_statement_message_handles_a_customer_credit_and_a_supplier():
    credit = WhatsAppService.build_statement_message({
        "kind": "customer", "party": {"name": "Client"},
        "closing_balance": Decimal("-150.00"),
    })
    assert "Crédit en votre faveur : 150.00 DH" in credit

    supplier = WhatsAppService.build_statement_message({
        "kind": "supplier", "party": {"name": "Fournisseur"},
        "closing_balance": Decimal("750.00"),
    })
    assert "relevé de compte fournisseur" in supplier
    assert "Solde : 750.00 DH" in supplier
