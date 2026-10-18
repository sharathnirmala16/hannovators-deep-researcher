"""Portable path-component checks shared by schemas and artifact I/O."""

from __future__ import annotations

import re

_WINDOWS_RESERVED_NAMES = {
    "aux",
    "clock$",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
}
_WINDOWS_RESERVED_DEVICE_RE = re.compile(r"^(?:com|lpt)[1-9¹²³]$")
_WINDOWS_INVALID_CHARACTERS = frozenset('<>"|?*')


def check_portable_path_component(component: str) -> None:
    """Reject Windows ADS syntax, invalid characters, and reserved device names."""
    if (
        not component
        or ":" in component
        or any(character in _WINDOWS_INVALID_CHARACTERS for character in component)
        or component.endswith((" ", "."))
    ):
        raise ValueError("path component is not portable to Windows")

    device_stem = component.split(".", maxsplit=1)[0].rstrip(" .").casefold()
    if (
        device_stem in _WINDOWS_RESERVED_NAMES
        or _WINDOWS_RESERVED_DEVICE_RE.fullmatch(device_stem) is not None
    ):
        raise ValueError("path component is a reserved Windows device name")
