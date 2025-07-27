FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements并安装Python依赖
COPY environment.yml .
RUN pip install --no-cache-dir \
    flask \
    flask-sqlalchemy \
    flask-login \
    werkzeug \
    python-dotenv \
    flask-cors \
    gunicorn \
    pycryptodome \
    python-multipart \
    tqdm \
    flask-wtf \
    flask-session

# 复制应用代码
COPY . .

# 创建默认数据目录
RUN mkdir -p /data/data

# 设置默认环境变量
ENV FLASK_CONFIG=production
ENV PORT=5000
ENV ENV_FILE=/app/.env
ENV DATA_DIR=/data

# 暴露端口
EXPOSE $PORT

# 使用gunicorn运行应用
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 run:app"]