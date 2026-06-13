# 星隧 VPN 控制面 FastAPI 后端镜像
# 仅承载控制面（API/DB 访问/官网/Admin）；wireguard-tools 只用于生成客户端密钥，
# 控制面不创建隧道接口、不承载 VPN 转发。
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 控制面签发边缘节点配置时需要 `wg genkey/pubkey` 生成客户端密钥。
RUN apt-get update \
    && apt-get install -y --no-install-recommends wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# 运行期依赖与 pyproject 保持单一来源；psycopg[binary] 自带二进制，无需系统 libpq。
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# 非 root 运行
RUN useradd -r -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 仅监听容器内网，外部由 Caddy 反代。worker 数针对 2GB RAM 控制在 2。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
