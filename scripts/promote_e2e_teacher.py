"""Promote the dedicated E2E account locally; this is a test fixture, not an API."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.auth.models import Permission, User
from backend.app.auth.permissions import DEFAULT_PERMISSIONS
from backend.app.importing.db import get_engine


def main() -> int:
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.username == "e2e_teacher"))
        if user is None:
            print("请先在 E2E 里注册 e2e_teacher（跑一次 npx playwright test 即可）")
            return 1

        permissions = DEFAULT_PERMISSIONS["teacher"]
        user.role = "teacher"
        session.execute(delete(Permission).where(Permission.user_id == user.user_id))
        session.add_all(
            Permission(
                permission_id=uuid.uuid4().hex,
                user_id=user.user_id,
                permission=permission,
                resource="",
                granted_by="e2e-fixture",
            )
            for permission in permissions
        )
        session.commit()
        print(f"role={user.role} permissions={len(permissions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
