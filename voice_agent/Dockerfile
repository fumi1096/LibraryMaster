FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY *.py .

# 容器内默认非交互模式（可被 docker-compose 覆盖）
CMD ["python3", "main.py", "--no-stream"]
