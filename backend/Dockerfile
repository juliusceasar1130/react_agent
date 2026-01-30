# 使用Python 3.12-slim镜像
FROM python:3.12-slim

# 设置工作目录为/app/backend
WORKDIR /app/backend

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt（从项目根目录）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制backend目录的所有文件到/app/backend
COPY backend/ /app/backend/

# 暴露端口
EXPOSE 8000

# 增加 PYTHONPATH，防止 Python 找不到模块
ENV PYTHONPATH=/app/backend

# 启动命令（在/app/backend目录下，可以找到app模块）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
