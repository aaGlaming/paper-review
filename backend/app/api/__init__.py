# 接入层。
# 声明赛题目录要求的路径：GET /api/contests、POST /api/imports、
# 赛题发布与归档、复制下一版量规、发布量规。
# 声明评审的三条路径：POST /api/reviews 创建、POST /api/reviews/{review_id}/resume 继续、
# GET /api/reviews/{review_id} 读取；外加样例与评测两条只读路径。
# 导入路径固定为 POST /api/imports，不提供第二个导入路径，也不实现上传文件与文件解析。

from .app import app, create_app

__all__ = ["app", "create_app"]
