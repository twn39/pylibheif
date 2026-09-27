"""Dynamic dictionary-style parameters proxy for HeifEncoder."""

from __future__ import annotations
import threading
import weakref
from typing import Any
from ._pylibheif import HeifEncoder, HeifEncoderParameterType


class HeifEncoderParametersProxy:
    """Proxy class providing dict-like access to HeifEncoder parameters."""

    def __init__(self, encoder: HeifEncoder):
        self._encoder_ref = weakref.ref(encoder)
        # Cache the metadata of parameters for quick lookup and local validation
        self._metadata = {p.name: p for p in encoder._list_parameters()}

    @property
    def _encoder(self) -> HeifEncoder:
        enc = self._encoder_ref()
        if enc is None:
            raise ReferenceError(
                "The underlying HeifEncoder has been garbage collected"
            )
        return enc

    def __getitem__(self, name: str):
        if name not in self._metadata:
            raise KeyError(
                f"Parameter '{name}' not found on encoder '{self._encoder.name}'"
            )
        param = self._metadata[name]
        if param.type == HeifEncoderParameterType.Integer:
            return self._encoder.get_integer_parameter(name)
        elif param.type == HeifEncoderParameterType.Boolean:
            return self._encoder.get_boolean_parameter(name)
        elif param.type == HeifEncoderParameterType.String:
            return self._encoder.get_string_parameter(name)
        else:
            return self._encoder.get_parameter(name)

    def __setitem__(self, name: str, value: Any):
        if name not in self._metadata:
            # Allow pass-through for prefixed parameters (e.g. x265:ctu)
            if ":" in name:
                self._encoder.set_parameter(name, str(value))
                return
            raise KeyError(
                f"Parameter '{name}' not found on encoder '{self._encoder.name}'"
            )

        param = self._metadata[name]
        if param.type == HeifEncoderParameterType.Integer:
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Parameter '{name}' requires an integer value, got {type(value)}"
                )
            int_val = int(value)
            # Validate ranges/values if they exist
            if param.valid_integer_range is not None:
                min_v, max_v = param.valid_integer_range
                if not (min_v <= int_val <= max_v):
                    raise ValueError(
                        f"Value {int_val} for parameter '{name}' is out of range [{min_v}, {max_v}]"
                    )
            if param.valid_integer_values is not None:
                if int_val not in param.valid_integer_values:
                    raise ValueError(
                        f"Value {int_val} for parameter '{name}' is not in valid values {param.valid_integer_values}"
                    )
            self._encoder.set_integer_parameter(name, int_val)

        elif param.type == HeifEncoderParameterType.Boolean:
            if not isinstance(value, bool):
                raise TypeError(
                    f"Parameter '{name}' requires a boolean value, got {type(value)}"
                )
            self._encoder.set_boolean_parameter(name, value)

        elif param.type == HeifEncoderParameterType.String:
            str_val = str(value)
            if param.valid_string_values is not None:
                if str_val not in param.valid_string_values:
                    raise ValueError(
                        f"Value '{str_val}' for parameter '{name}' is not in valid values {param.valid_string_values}"
                    )
            self._encoder.set_string_parameter(name, str_val)

    def __contains__(self, name: str) -> bool:
        return name in self._metadata or ":" in name

    def keys(self):
        return self._metadata.keys()

    def values(self):
        return [self._metadata[k] for k in self._metadata]

    def items(self):
        return [(k, self._metadata[k]) for k in self._metadata]

    def __len__(self) -> int:
        return len(self._metadata)

    def __iter__(self):
        return iter(self._metadata)

    def __repr__(self) -> str:
        items_repr = ", ".join(f"'{k}': {self[k]}" for k in self.keys())
        return f"HeifEncoderParameters({{{items_repr}}})"


_encoder_parameters_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_encoder_parameters_lock = threading.Lock()


def get_encoder_parameters(encoder: HeifEncoder) -> HeifEncoderParametersProxy:
    """Retrieve or create cached parameter proxy for a HeifEncoder instance."""
    try:
        with _encoder_parameters_lock:
            if encoder not in _encoder_parameters_cache:
                _encoder_parameters_cache[encoder] = HeifEncoderParametersProxy(encoder)
            return _encoder_parameters_cache[encoder]
    except TypeError:
        # Fallback if not weak-referenceable
        return HeifEncoderParametersProxy(encoder)
