"""Translate Homevolt API errors into user-facing Home Assistant errors."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from homeassistant.exceptions import HomeAssistantError

from .api import (
    HomevoltApiError,
    HomevoltAuthError,
    HomevoltCommandError,
    HomevoltConnectionError,
    HomevoltNotLocalModeError,
    HomevoltRateLimitError,
)
from .const import DOMAIN


def _error(key: str, placeholders: dict[str, str] | None = None) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders,
    )


@contextmanager
def translate_api_errors(host: str) -> Iterator[None]:
    """Re-raise Homevolt API errors as translated HomeAssistantErrors.

    Subclass order matters: every error derives from HomevoltApiError, which is
    the generic fallback.
    """
    try:
        yield
    except HomevoltNotLocalModeError as err:
        raise _error("not_local_mode") from err
    except HomevoltCommandError as err:
        raise _error("command_failed", {"error": str(err)}) from err
    except HomevoltAuthError as err:
        raise _error("invalid_auth", {"host": host}) from err
    except HomevoltRateLimitError as err:
        raise _error("rate_limited") from err
    except HomevoltConnectionError as err:
        raise _error("cannot_connect", {"host": host}) from err
    except HomevoltApiError as err:
        raise _error("api_error", {"error": str(err)}) from err
