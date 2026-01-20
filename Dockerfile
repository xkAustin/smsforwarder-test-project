# syntax=docker/dockerfile:1
FROM python:3.12-slim

# 基础环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 设置工作目录
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# 安装 uv（官方推荐方式之一：curl 安装）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# 只拷贝依赖文件，利用缓存
COPY pyproject.toml uv.lock ./

#安装依赖
RUN uv sync --frozen

# 再拷贝代码
COPY . .

CMD ["bash"]
