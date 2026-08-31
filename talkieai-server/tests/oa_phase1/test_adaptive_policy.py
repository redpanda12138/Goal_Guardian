import pytest

from adaptive_policy import CRITERIA, assess_transition


def assessment(stage, decision="advance", missing=()):
    return {
        "decision": decision,
        "criteria": {key: key not in missing for key in CRITERIA[stage]},
        "evidence": {key: ["m1"] if key not in missing else [] for key in CRITERIA[stage]},
        "reason": "The user has supplied the required information.",
    }


@pytest.mark.parametrize("count", [3, 5, 6])
def test_opening_can_advance_before_at_or_after_reference(count):
    result = assess_transition("SOA", count, assessment("SOA"), {"m1"})
    assert result["next_agent"] == "GRA"


def test_reference_count_does_not_force_a_transition():
    result = assess_transition("SOA", 5, assessment("SOA", missing=("willingness",)), {"m1"})
    assert result["next_agent"] == "SOA"
    assert result["reason"] == "criteria_incomplete"


def test_unknown_evidence_and_string_booleans_fail_closed():
    item = assessment("SOA")
    assert assess_transition("SOA", 5, item, {"other"})["reason"] == "invalid_assessment"
    item["criteria"]["willingness"] = "true"
    assert assess_transition("SOA", 5, item, {"m1"})["reason"] == "invalid_assessment"


def test_early_floor_and_pending_writes_block_handoff():
    assert assess_transition("SOA", 1, assessment("SOA"), {"m1"})["next_agent"] == "SOA"
    assert assess_transition("GRA", 8, assessment("GRA"), {"m1"}, blocking=True)["reason"] == "pending_action"


def test_upper_review_point_offers_recovery_without_forcing_handoff():
    result = assess_transition("GRA", 10, assessment("GRA", "clarify", ("next_action",)), {"m1"})
    assert result["next_agent"] == "GRA"
    assert result["needs_recovery"] is True


@pytest.mark.parametrize("bad", [None, {}, {"decision": "close"}, "advance"])
def test_malformed_assessment_never_completes_a_stage(bad):
    assert assess_transition("SCA", 2, bad, {"m1"})["next_agent"] == "SCA"


def test_non_string_decision_is_invalid_instead_of_crashing():
    item = assessment("SOA")
    item["decision"] = []
    assert assess_transition("SOA", 4, item, {"m1"})["reason"] == "invalid_assessment"
