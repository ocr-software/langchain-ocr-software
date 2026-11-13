"""The release files agree with each other."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_publish_workflow_is_trusted_publishing_with_tests_and_tag_check_before_upload():
    """Review 13.11.2026: no token, OIDC, environment pypi, release trigger, tag = version, tests before the upload step."""
    wf = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    for needed in ("types: [published]", "id-token: write", "environment: pypi", "GITHUB_REF_NAME"):
        assert needed in wf
    assert "password" not in wf and "secrets." not in wf
    assert wf.index("GITHUB_REF_NAME") < wf.index("pytest") < wf.index("twine check") < wf.index("gh-action-pypi-publish")
