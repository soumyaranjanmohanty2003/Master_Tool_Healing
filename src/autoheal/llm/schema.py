"""Validates the raw JSON object returned by the LLM before it's trusted."""

from __future__ import annotations

from autoheal.models import Confidence, FixType

REQUIRED_KEYS = {"root_cause", "confidence", "fix_type", "explanation", "fixed_code"}


class InvalidLLMResponse(ValueError):
    pass


def validate_llm_response(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise InvalidLLMResponse(f"Expected a JSON object, got {type(raw).__name__}")

    missing = REQUIRED_KEYS - raw.keys()
    if missing:
        raise InvalidLLMResponse(f"Missing required keys: {sorted(missing)}")

    try:
        confidence = Confidence(raw["confidence"])
    except ValueError as exc:
        raise InvalidLLMResponse(f"Invalid confidence: {raw['confidence']!r}") from exc

    try:
        fix_type = FixType(raw["fix_type"])
    except ValueError as exc:
        raise InvalidLLMResponse(f"Invalid fix_type: {raw['fix_type']!r}") from exc

    fixed_code = raw["fixed_code"]
    if fix_type == FixType.NO_FIX_POSSIBLE:
        fixed_code = None
    elif not isinstance(fixed_code, str) or not fixed_code.strip():
        raise InvalidLLMResponse("fixed_code must be a non-empty string when a fix is proposed")

    if not isinstance(raw["root_cause"], str) or not raw["root_cause"].strip():
        raise InvalidLLMResponse("root_cause must be a non-empty string")

    return {
        "root_cause": raw["root_cause"],
        "confidence": confidence,
        "fix_type": fix_type,
        "explanation": raw.get("explanation", ""),
        "fixed_code": fixed_code,
    }
