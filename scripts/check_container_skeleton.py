"""Statically check the P24 container skeleton without invoking Docker."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.yaml"
DOCKERFILE = ROOT / "backend" / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
REQUIRED_SERVICES = {"frontend", "backend", "mysql", "chroma"}


def main() -> int:
    checks: list[tuple[str, bool]] = []
    raw = COMPOSE.read_text(encoding="utf-8") if COMPOSE.is_file() else ""
    parsed: dict[str, object] = {}

    try:
        parsed_value = yaml.safe_load(raw)
        parsed = parsed_value if isinstance(parsed_value, dict) else {}
        checks.append(("compose.yaml parses with yaml.safe_load", True))
    except (yaml.YAMLError, UnicodeError) as exc:
        checks.append((f"compose.yaml parses with yaml.safe_load ({type(exc).__name__})", False))

    services = parsed.get("services")
    services = services if isinstance(services, dict) else {}
    checks.append(("four required service keys exist", REQUIRED_SERVICES <= services.keys()))
    for service_name in sorted(REQUIRED_SERVICES):
        service = services.get(service_name)
        checks.append(
            (
                f"{service_name} service contains UNVERIFIED string",
                isinstance(service, dict)
                and isinstance(service.get("x-verification"), str)
                and "UNVERIFIED" in service["x-verification"],
            )
        )

    checks.append(("compose has no :latest image tag", ":latest" not in raw))
    wildcard_origins = re.search(
        r"(?im)^\s*allow_origins?\s*:\s*(?:\[\s*)?[\"']\*[\"']", raw
    )
    checks.append(("compose has no wildcard origins", wildcard_origins is None))
    secret_assignments = re.finditer(
        r"(?i)(password|secret|api_key)\s*:\s*(\S+)", raw
    )
    hardcoded_secret = any(
        not match.group(2).startswith("${") for match in secret_assignments
    )
    checks.append(("compose has no hard-coded password/secret/api_key", not hardcoded_secret))

    dockerfile = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.is_file() else ""
    docker_lines = dockerfile.splitlines()
    checks.append(("backend/Dockerfile exists and first line is UNVERIFIED", bool(docker_lines) and "UNVERIFIED" in docker_lines[0]))
    checks.append(("Dockerfile uses python:3.11 base image", "FROM python:3.11" in dockerfile))
    checks.append(("Dockerfile copies requirements before installing", dockerfile.find("COPY requirements.txt") >= 0 and dockerfile.find("RUN pip install") > dockerfile.find("COPY requirements.txt")))
    checks.append(("Dockerfile copies app code after dependency install", dockerfile.find("COPY app") > dockerfile.find("RUN pip install")))
    checks.append(("Dockerfile runs as non-root USER", re.search(r"(?m)^USER\s+\w+", dockerfile) is not None))
    checks.append(("Dockerfile uses --factory", "--factory" in dockerfile))
    checks.append(("Dockerfile does not COPY .env", re.search(r"(?im)^\s*COPY\s+.*\.env", dockerfile) is None))

    ignore = DOCKERIGNORE.read_text(encoding="utf-8") if DOCKERIGNORE.is_file() else ""
    checks.append((".dockerignore exists and includes required exclusions", DOCKERIGNORE.is_file() and all(item in ignore.splitlines() for item in (".env", "chroma_data", "logs", "node_modules"))))

    for description, passed in checks:
        print(f"[{'ok' if passed else 'fail'}] {description}")
    failed = sum(not passed for _, passed in checks)
    print(f"summary checks={len(checks)} issues={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
