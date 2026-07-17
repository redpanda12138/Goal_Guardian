"""Pure routing rules that characterize the legacy MAS message path."""
from typing import Any, Mapping, Optional


def select_legacy_mas_agent(turn_index: int) -> str:
    """Return the legacy agent selected for an established MAS turn."""
    if turn_index <= 5:
        return "soa"
    if turn_index <= 13:
        return "gra"
    return "sca"


def should_retry_soa_with_gra(result: Optional[Mapping[str, Any]]) -> bool:
    """Identify the sole legacy SOA-to-GRA compatibility retry condition."""
    return bool(
        result
        and result.get("status") == "error"
        and "should be sent to GRA" in str(result.get("reason", ""))
    )
