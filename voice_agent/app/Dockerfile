FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 app/ 下所有 Python 文件到 /app/（供 import 直接使用）
COPY app/*.py .
# 复制 static/ 目录（前端静态文件）
COPY app/static ./static/
# 复制根目录的共享配置
COPY config.py .
COPY .env .

# FastAPI + Uvicorn 入口
CMD ["python3", "agent_server.py"]
