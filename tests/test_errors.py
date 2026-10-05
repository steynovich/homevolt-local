"""Tests for API error translation."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.homevolt_local.api import (
    HomevoltApiError,
    HomevoltAuthError,
    HomevoltCommandError,
    HomevoltConnectionError,
    HomevoltNotLocalModeError,
    HomevoltRateLimitError,
)
from custom_components.homevolt_local.const import DOMAIN
from custom_components.homevolt_local.errors import translate_api_errors


@pytest.mark.parametrize(
    ("error", "key", "placeholders"),
    [
        (HomevoltNotLocalModeError("x"), "not_local_mode", None),
        (HomevoltCommandError("bad"), "command_failed", {"error": "bad"}),
        (HomevoltAuthError("x"), "invalid_auth", {"host": "h"}),
        (HomevoltRateLimitError("x"), "rate_limited", None),
        (HomevoltConnectionError("x"), "cannot_connect", {"host": "h"}),
        (HomevoltApiError("boom"), "api_error", {"error": "boom"}),
    ],
)
def test_translate_api_errors(error: Exception, key: str, placeholders: dict | None) -> None:
    """Each API error maps to a translated HomeAssistantError."""
    with pytest.raises(HomeAssistantError) as exc_info, translate_api_errors("h"):
        raise error

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == placeholders
    assert exc_info.value.__cause__ is error


def test_translate_api_errors_passes_through_success_and_other_errors() -> None:
    """No error is a no-op and unrelated exceptions are untouched."""
    with translate_api_errors("h"):
        pass

    with pytest.raises(KeyError), translate_api_errors("h"):
        raise KeyError("x")
