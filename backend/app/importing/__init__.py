# 赛题数据包导入。
# 读 data/contests/{contest_id}/ 下的五个 JSON（contest、constraints、rubric、pitfalls、exemplars），
# 整包校验通过才写库；缺字段、权重合计不是 100、检查类型未注册或档位不全时整包拒绝，已发布数据不变。
# 提供发布、归档、复制下一版量规、发布量规与列表。不按题号写分支，差异只来自 JSON。
# 连接串只从环境变量 MYSQL_DSN 读，建表用 metadata.create_all()，不用 alembic。

from .catalog import (
    BAND_NAMES,
    CHECK_TYPES,
    DIMENSION_CODES,
    CatalogError,
    CatalogStateError,
    PackageError,
    archive_contest,
    copy_rubric_as_draft,
    import_package,
    list_contests,
    publish_contest,
    publish_rubric,
    validate_package,
)
from .db import create_schema, get_dsn, get_engine, session_scope

__all__ = [
    "BAND_NAMES",
    "CHECK_TYPES",
    "DIMENSION_CODES",
    "CatalogError",
    "CatalogStateError",
    "PackageError",
    "archive_contest",
    "copy_rubric_as_draft",
    "create_schema",
    "get_dsn",
    "get_engine",
    "import_package",
    "list_contests",
    "publish_contest",
    "publish_rubric",
    "session_scope",
    "validate_package",
]
