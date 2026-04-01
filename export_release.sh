#!/bin/bash

# 设置名称和目标目录
IMAGE_NAME="soar-mcp:latest"
RELEASE_DIR="soar-mcp-release"
TAR_FILE="${RELEASE_DIR}.tar.gz"

echo "==========================================="
echo "   SOAR-MCP Docker 离线包导出工具"
echo "==========================================="

# 1. 检查镜像是否存在
if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    echo "[错误] 找不到本地镜像 ${IMAGE_NAME}，请确保已经执行过 docker-compose build"
    exit 1
fi

# 2. 准备发布目录结构
echo "[1/4] 准备离线部署包目录结构..."
rm -rf "${RELEASE_DIR}" "${TAR_FILE}"
mkdir -p "${RELEASE_DIR}/logs"
touch "${RELEASE_DIR}/soar_mcp.db"

# 3. 复制配置文件
echo "[2/4] 拷贝 docker-compose.yml..."
cp docker-compose.yml "${RELEASE_DIR}/"

# 4. 导出 Docker 镜像
echo "[3/4] 正在导出 Docker 镜像 (文件偏大，请耐心等待)..."
docker save -o "${RELEASE_DIR}/soar-mcp-image.tar" "${IMAGE_NAME}"

# 5. 复制一键导入安装脚本
echo "[4/4] 拷贝 install.sh 一键安装脚本..."
cp import_install.sh "${RELEASE_DIR}/install.sh"
chmod +x "${RELEASE_DIR}/install.sh"

# 6. 打包压缩文件夹
echo "=> 正在将目录打包为 ${TAR_FILE}..."
tar -czvf "${TAR_FILE}" "${RELEASE_DIR}" > /dev/null
rm -rf "${RELEASE_DIR}"

echo "==========================================="
echo " ✅ 导出完毕！"
echo " 发布文件: ${TAR_FILE}"
echo " 你可以将该压缩包复制到其他机器，解压后执行里面的 ./install.sh 即可一键恢复部署"
echo "==========================================="
