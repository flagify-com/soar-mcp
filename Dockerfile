FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，确保 Python 输出直接打印到终端，不缓冲
ENV PYTHONUNBUFFERED=1

# 更新 apt 并安装一些基础编译依赖（如果某些 Python 包需要 C 扩展编译）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制环境配置文件，利用 Docker 缓存加速后续构建
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目到工作目录
# (注：.dockerignore 会过滤掉 venv, logs, 数据库等不必要文件)
COPY . .

# 暴露所需的端口
# 12345: MCP 服务连接端口
# 12346: Web 管理后台端口
EXPOSE 12345 12346

# 设定默认的容器启动命令
CMD ["python3", "soar_mcp_server.py"]
