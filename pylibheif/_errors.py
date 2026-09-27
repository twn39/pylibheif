"""Error string formatting and diagnostic extensions for HeifError."""

from __future__ import annotations
from ._pylibheif import HeifError


def _heif_error_str(self: HeifError) -> str:
    code_name = getattr(self, "code_name", "Unknown")
    code_val = getattr(self, "code", -1)
    subcode_val = getattr(self, "subcode", -1)
    msg = Exception.__str__(self)
    return f"[{self.__class__.__name__}] {code_name} (code={code_val}, subcode={subcode_val}): {msg}"


def _heif_error_repr(self: HeifError) -> str:
    code_name = getattr(self, "code_name", "Unknown")
    code_val = getattr(self, "code", -1)
    subcode_val = getattr(self, "subcode", -1)
    msg = Exception.__str__(self)
    return f"<{self.__class__.__name__} code_name='{code_name}' code={code_val} subcode={subcode_val} message={msg!r}>"


def patch_error_formatting() -> None:
    """Attach human-readable and structured formatting to HeifError base class."""
    setattr(HeifError, "__str__", _heif_error_str)
    setattr(HeifError, "__repr__", _heif_error_repr)
