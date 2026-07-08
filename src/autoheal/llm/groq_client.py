"""Groq-backed diagnosis: turns a failure + source context into a `Diagnosis`."""

from __future__ import annotations

import json

from groq import APIStatusError, Groq

from autoheal.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from autoheal.llm.schema import InvalidLLMResponse, validate_llm_response
from autoheal.models import Diagnosis, FailureReport, FixAttempt, FixType, SourceContext
from autoheal.patch.differ import compute_diff

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_TEMPERATURE = 0.2


class DiagnosisError(RuntimeError):
    pass


class GroqDiagnosisClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        if not api_key:
            raise ValueError("Groq API key is required")
        self._client = Groq(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def diagnose(
        self,
        failure: FailureReport,
        context: SourceContext,
        previous_attempts: list[FixAttempt] | None = None,
    ) -> Diagnosis:
        user_prompt = build_user_prompt(failure, context, previous_attempts)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except APIStatusError as exc:
            raise DiagnosisError(f"Groq API request failed: {exc}") from exc

        content = response.choices[0].message.content
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise DiagnosisError(f"Groq did not return valid JSON: {exc}\nContent: {content!r}") from exc

        try:
            parsed = validate_llm_response(raw)
        except InvalidLLMResponse as exc:
            raise DiagnosisError(str(exc)) from exc

        diff = None
        if parsed["fix_type"] != FixType.NO_FIX_POSSIBLE and parsed["fixed_code"]:
            diff = compute_diff(context.full_text, parsed["fixed_code"], context.file_path)

        return Diagnosis(
            root_cause=parsed["root_cause"],
            confidence=parsed["confidence"],
            fix_type=parsed["fix_type"],
            explanation=parsed["explanation"],
            diff=diff,
        )
