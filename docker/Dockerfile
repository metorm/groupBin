FROM python:3.13-slim

WORKDIR /app

# 定义参数，允许使用国内pip镜像加速依赖安装
ARG USE_CHINA_PIP_MIRROR=false
ARG PIP_MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 定义参数，允许使用国内apt镜像加速依赖安装
ARG USE_CHINA_APT_MIRROR=false
ARG DEBIAN_APT_MIRROR_URL=mirrors.aliyun.com

# 配置pip镜像源（如果启用）
RUN if [ "$USE_CHINA_PIP_MIRROR" = "true" ]; then \
    pip config set global.index-url $PIP_MIRROR_URL; \
    fi

# 配置国内apt镜像源并安装系统依赖
RUN if [ "$USE_CHINA_APT_MIRROR" = "true" ]; then \
    sed -i "s/deb.debian.org/$DEBIAN_APT_MIRROR_URL/g" /etc/apt/sources.list.d/debian.sources && \
    sed -i "s/security.debian.org/$DEBIAN_APT_MIRROR_URL/g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean

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
