# 接入层。
# 本版只声明赛题目录需要的路径：GET /api/contests、POST /api/imports、
# 赛题发布与归档、复制下一版量规、发布量规。
# 导入路径固定为 POST /api/imports，不提供第二个导入路径。
# 本版不实现上传文件，也不实现 /api/reviews、样例与评测接口（属后续版本）。

from .app import app, create_app

__all__ = ["app", "create_app"]
