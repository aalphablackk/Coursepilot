
from dataclasses import fields, is_dataclass
from typing import Any

from core.text_normalizer import normalize_generated_text


def normalize_output(value: Any) -> Any:
    """
    Recursively normalize text in dataclasses, lists, tuples, and dictionaries.
    Preserves the existing output schema and non-text values.
    """
    if isinstance(value, str):
        return normalize_generated_text(value)

    if is_dataclass(value) and not isinstance(value, type):
        updates = {
            field.name: normalize_output(getattr(value, field.name))
            for field in fields(value)
        }
        return type(value)(**updates)

    if isinstance(value, list):
        return [normalize_output(item) for item in value]

    if isinstance(value, tuple):
        return tuple(normalize_output(item) for item in value)

    if isinstance(value, dict):
        return {
            key: normalize_output(item)
            for key, item in value.items()
        }

    return value
