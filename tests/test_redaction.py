from autoheal.context.redaction import redact


def test_redacts_api_key_assignment():
    text = 'const config = { api_key: "sk-abcdef1234567890" };'
    assert "sk-abcdef1234567890" not in redact(text)


def test_redacts_bearer_token():
    text = "Authorization: Bearer abc123.def456-ghi_789"
    assert "abc123.def456-ghi_789" not in redact(text)


def test_redacts_jwt():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dQw4w9WgXcQ_abc123"
    assert jwt not in redact(f"token={jwt}")


def test_redacts_aws_key():
    text = "AWS key: AKIAABCDEFGHIJKLMNOP"
    assert "AKIAABCDEFGHIJKLMNOP" not in redact(text)


def test_redacts_url_credentials():
    text = "cloning https://user:hunter2@example.com/repo.git"
    result = redact(text)
    assert "hunter2" not in result


def test_leaves_normal_text_untouched():
    text = "expect(page.locator('#submit-btn')).toBeVisible();"
    assert redact(text) == text


def test_empty_string_passthrough():
    assert redact("") == ""
