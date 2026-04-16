# 使用Python 3.12-slim镜像
FROM python:3.12-slim

# 2026-04-02 Asia/Shanghai: 与仓库内 `backend.app...` 绝对导入保持一致
# 将工作目录切到 /app，并把 /app 作为 Python 包根路径。
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt（从项目根目录）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制 backend 目录的所有文件到 /app/backend
COPY backend/ /app/backend/

# 暴露端口
EXPOSE 8000

# 增加 PYTHONPATH，确保容器内可解析 `backend.app...` 绝对导入
ENV PYTHONPATH=/app

# 启动命令：按仓库真实包路径启动 FastAPI
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
