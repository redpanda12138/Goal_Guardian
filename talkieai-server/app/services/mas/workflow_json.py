"""Validation helpers for JSON-only workflow data."""
import math
from typing import Any


def ensure_json_value(value: Any) -> Any:
    """Return a JSON value or raise ValueError for unsupported data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise ValueError("JSON floats must be finite")
    if isinstance(value, list):
        return [ensure_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: ensure_json_value(item) for key, item in value.items()}
    raise ValueError("value is not JSON serializable")


def ensure_json_object(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("value must be a JSON object")
    return ensure_json_value(value)
