import json
from types import SimpleNamespace

import pytest

from autoheal.llm.groq_client import DiagnosisError, GroqDiagnosisClient
from autoheal.models import Confidence, FailureReport, FixType, SourceContext


def _fake_groq_response(payload: dict):
    message = SimpleNamespace(content=json.dumps(payload))
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture
def failure_and_context():
    failure = FailureReport(
        test_id="tests/example.spec.ts::user can sign in",
        test_name="user can sign in",
        file_path="tests/example.spec.ts",
        framework="playwright",
        language="typescript",
        error_message="Timeout waiting for selector text=Log In",
    )
    context = SourceContext(
        file_path="tests/example.spec.ts",
        language="typescript",
        full_text="test('x', () => { click('text=Log In'); });\n",
        snippet="test('x', () => { click('text=Log In'); });\n",
        snippet_start_line=1,
    )
    return failure, context


def test_diagnose_returns_diagnosis_with_computed_diff(monkeypatch, failure_and_context):
    failure, context = failure_and_context
    payload = {
        "root_cause": "Stale selector text",
        "confidence": "high",
        "fix_type": "selector_update",
        "explanation": "Updated selector to match current button text",
        "fixed_code": "test('x', () => { click('text=Sign In'); });\n",
    }

    client = GroqDiagnosisClient(api_key="fake-key")
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **kwargs: _fake_groq_response(payload),
    )

    diagnosis = client.diagnose(failure, context)

    assert diagnosis.confidence == Confidence.HIGH
    assert diagnosis.fix_type == FixType.SELECTOR_UPDATE
    assert diagnosis.diff is not None
    assert "+test('x', () => { click('text=Sign In'); });" in diagnosis.diff


def test_diagnose_handles_no_fix_possible(monkeypatch, failure_and_context):
    failure, context = failure_and_context
    payload = {
        "root_cause": "Looks like a real app regression",
        "confidence": "low",
        "fix_type": "no_fix_possible",
        "explanation": "",
        "fixed_code": None,
    }

    client = GroqDiagnosisClient(api_key="fake-key")
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **kwargs: _fake_groq_response(payload),
    )

    diagnosis = client.diagnose(failure, context)
    assert diagnosis.fix_type == FixType.NO_FIX_POSSIBLE
    assert diagnosis.diff is None


def test_diagnose_raises_on_invalid_json(monkeypatch, failure_and_context):
    failure, context = failure_and_context
    client = GroqDiagnosisClient(api_key="fake-key")

    bad_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
    )
    monkeypatch.setattr(client._client.chat.completions, "create", lambda **kwargs: bad_response)

    with pytest.raises(DiagnosisError):
        client.diagnose(failure, context)


def test_requires_api_key():
    with pytest.raises(ValueError):
        GroqDiagnosisClient(api_key="")
