import pytest

from autoheal.llm.schema import InvalidLLMResponse, validate_llm_response
from autoheal.models import Confidence, FixType


def test_validates_full_response():
    raw = {
        "root_cause": "Stale selector",
        "confidence": "high",
        "fix_type": "selector_update",
        "explanation": "Updated text selector to match new button copy",
        "fixed_code": "const x = 1;",
    }
    parsed = validate_llm_response(raw)
    assert parsed["confidence"] == Confidence.HIGH
    assert parsed["fix_type"] == FixType.SELECTOR_UPDATE
    assert parsed["fixed_code"] == "const x = 1;"


def test_no_fix_possible_allows_null_fixed_code():
    raw = {
        "root_cause": "Looks like a real product bug",
        "confidence": "low",
        "fix_type": "no_fix_possible",
        "explanation": "",
        "fixed_code": None,
    }
    parsed = validate_llm_response(raw)
    assert parsed["fixed_code"] is None


def test_missing_keys_raises():
    with pytest.raises(InvalidLLMResponse):
        validate_llm_response({"root_cause": "x"})


def test_invalid_confidence_raises():
    raw = {
        "root_cause": "x",
        "confidence": "very high",
        "fix_type": "selector_update",
        "explanation": "",
        "fixed_code": "code",
    }
    with pytest.raises(InvalidLLMResponse):
        validate_llm_response(raw)


def test_fix_proposed_without_code_raises():
    raw = {
        "root_cause": "x",
        "confidence": "high",
        "fix_type": "selector_update",
        "explanation": "",
        "fixed_code": None,
    }
    with pytest.raises(InvalidLLMResponse):
        validate_llm_response(raw)


def test_non_dict_raises():
    with pytest.raises(InvalidLLMResponse):
        validate_llm_response(["not", "a", "dict"])
