# UNVERIFIED: 本机未安装 Docker，本文件从未构建或运行过。仅为交付骨架。
FROM python:3.11-slim

WORKDIR /app

# Copy dependency metadata first so Docker can reuse the dependency layer cache.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy only application code; data, logs, secrets, and tests are intentionally excluded.
COPY app /app/backend/app

RUN useradd -m app && chown -R app /app
USER app

# --factory is required because create_app is an application factory, not a module-level ASGI app.
CMD ["uvicorn","backend.app.api.app:create_app","--factory","--host","0.0.0.0","--port","8077"]

# 镜像预期体积 ≥ 1GB（含 chromadb），属未验收范围的已知代价。
