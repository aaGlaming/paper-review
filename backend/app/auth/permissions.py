"""权限标识：全项目唯一的权限码出处，接口里不写字面量字符串。

默认权限集按 Phase-3 计划 §4.2 表格（学生 3 条、教师 7 条）：
计划正文「教师 6 条」是笔误，以表格为准——表格里教师 7 条全是 ✅。
"""

from __future__ import annotations

PERM_CREATE = "review:create"
PERM_READ_OWN = "review:read:own"
PERM_READ_ALL = "review:read:all"
PERM_CHAT = "chat:use"
PERM_DASHBOARD = "dashboard:view"
PERM_CONTEST = "contest:manage"
PERM_EVAL = "eval:view"

DEFAULT_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "student": (PERM_CREATE, PERM_READ_OWN, PERM_EVAL),
    "teacher": (
        PERM_CREATE,
        PERM_READ_OWN,
        PERM_READ_ALL,
        PERM_CHAT,
        PERM_DASHBOARD,
        PERM_CONTEST,
        PERM_EVAL,
    ),
}
