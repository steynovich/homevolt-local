"""Compatibility imports for the range of supported Home Assistant versions.

HA 2026.9 replaced voluptuous with probatio, and 2026.10 moved the button and
binary sensor device class enums into their `const` modules. Types are checked
against the newest HA; at runtime we fall back to the older locations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import probatio as vol
    from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
    from homeassistant.components.button.const import ButtonDeviceClass
else:
    try:
        import probatio as vol
    except ImportError:  # HA < 2026.9
        import voluptuous as vol

    try:
        from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
    except ImportError:  # HA < 2026.10
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    try:
        from homeassistant.components.button.const import ButtonDeviceClass
    except ImportError:  # HA < 2026.10
        from homeassistant.components.button import ButtonDeviceClass

__all__ = ["BinarySensorDeviceClass", "ButtonDeviceClass", "vol"]
