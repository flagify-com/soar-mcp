#!/bin/bash

echo "==========================================="
echo "   SOAR-MCP 快速导入与部署脚本"
echo "==========================================="

# 确保以当前脚本所在目录为工作目录
cd "$(dirname "$0")"

# 1. 加载镜像
echo "=> [1/2] 正在导入本地 Docker 镜像..."
docker load -i soar-mcp-image.tar

# 2. 启动服务 (同时兼容 docker-compose 和 docker compose V2)
echo "=> [2/2] 正在启动后台服务..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
elif docker compose version &> /dev/null; then
    docker compose up -d
else
    echo "[错误] 未检测到 docker-compose 控制台，请确保已安装 Docker Compose"
    exit 1
fi

echo "==========================================="
echo " 🎉 部署完成！"
echo " 请通过 docker ps 查看运行状态"
echo " 管理后台: http://<这是你的服务器IP>:12346/admin"
echo " MCP服务: http://<这是你的服务器IP>:12345/mcp"
echo " (管理员初始密码请执行: docker compose logs -f soar-mcp-server 获取)"
echo "==========================================="
