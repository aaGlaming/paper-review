from pathlib import Path


def test_agent_package_source_has_no_http_client_imports_or_references():
    package_dir = Path(__file__).resolve().parents[2] / "app" / "agent"
    forbidden = ("httpx", "requests", "urllib")

    for source in package_dir.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), source
