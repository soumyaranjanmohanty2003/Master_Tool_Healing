from autoheal.llm.prompts import build_user_prompt
from autoheal.models import FailureReport, SourceContext


def make_failure(framework: str) -> FailureReport:
    return FailureReport(
        test_id="flows/login.yaml",
        test_name="login flow",
        file_path="flows/login.yaml",
        framework=framework,
        language="yaml",
        error_message="Element not found: Log In",
    )


def make_context(text: str = "appId: com.example\n---\n- tapOn: Log In\n") -> SourceContext:
    return SourceContext(
        file_path="flows/login.yaml", language="yaml", full_text=text, snippet=text, snippet_start_line=1
    )


def test_maestro_prompt_includes_config_header_reminder():
    prompt = build_user_prompt(make_failure("maestro"), make_context())
    assert "config header" in prompt
    assert "appId" in prompt


def test_non_maestro_prompt_omits_config_header_reminder():
    prompt = build_user_prompt(make_failure("playwright-js"), make_context())
    assert "config header" not in prompt
