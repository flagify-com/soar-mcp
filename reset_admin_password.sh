#!/bin/bash

# SOAR 管理员密码重置/修改脚本 v2.0
# 支持：随机生成新密码 / 指定新密码
# 使用 bcrypt 进行密码哈希

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
check_venv() {
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        print_warning "未找到虚拟环境，使用系统 Python"
    fi

    if ! python3 -c "import bcrypt" 2>/dev/null; then
        print_error "缺少 bcrypt 模块，请执行: pip install bcrypt"
        exit 1
    fi
}

# 检查数据库
check_database() {
    if [ ! -f "soar_mcp.db" ]; then
        print_error "数据库文件 soar_mcp.db 不存在"
        print_info "请先启动一次服务器以创建数据库：python3 soar_mcp_server.py"
        exit 1
    fi
}

# 执行密码操作的 Python 脚本
do_password_operation() {
    local password="$1"
    python3 << PYEOF
import sys
sys.path.insert(0, '.')
from models import db_manager
from auth_utils import AuthManager

auth = AuthManager()
password = """${password}"""

if password:
    new_password = password
else:
    new_password = auth.generate_admin_password()

hashed = auth.hash_password(new_password)
success = db_manager.create_admin_password(hashed, "脚本重置的管理员密码")

if success:
    print(f"SUCCESS|{new_password}")
else:
    print("ERROR|密码更新失败，请检查数据库")
PYEOF
}

# 显示用法
show_usage() {
    echo
    echo "用法："
    echo "  $0              交互模式（推荐）"
    echo "  $0 --random     直接生成随机密码"
    echo "  $0 --set <pwd>  设置指定密码"
    echo
}

# 交互模式
interactive_mode() {
    echo
    print_warning "⚠️  此操作将重置管理员密码，旧密码将立即失效"
    echo
    echo "请选择操作："
    echo "  1) 生成随机密码"
    echo "  2) 设置指定密码"
    echo "  q) 取消"
    echo
    read -p "请输入选项 [1/2/q]: " choice

    case "$choice" in
        1)
            do_reset ""
            ;;
        2)
            echo
            read -s -p "请输入新密码: " pwd1
            echo
            read -s -p "请确认新密码: " pwd2
            echo

            if [ -z "$pwd1" ]; then
                print_error "密码不能为空"
                exit 1
            fi

            if [ "$pwd1" != "$pwd2" ]; then
                print_error "两次输入的密码不一致"
                exit 1
            fi

            if [ ${#pwd1} -lt 8 ]; then
                print_warning "密码长度建议不少于8位"
                read -p "仍要继续? [y/N]: " confirm
                if [[ ! $confirm =~ ^[Yy]$ ]]; then
                    print_info "操作已取消"
                    exit 0
                fi
            fi

            do_reset "$pwd1"
            ;;
        q|Q|"")
            print_info "操作已取消"
            exit 0
            ;;
        *)
            print_error "无效选项"
            exit 1
            ;;
    esac
}

# 执行重置
do_reset() {
    local password="$1"

    print_info "正在更新密码..."
    result=$(do_password_operation "$password" 2>/dev/null)

    if [[ $result == SUCCESS\|* ]]; then
        new_password=${result#SUCCESS|}
        echo
        print_success "🎉 管理员密码已更新！"
        echo
        echo "======================================"
        echo -e "  管理员密码: ${YELLOW}${new_password}${NC}"
        echo "======================================"
        echo
        print_info "密码立即生效，无需重启服务"
        print_info "管理后台: http://127.0.0.1:12346/admin"
        echo
    else
        error_msg=${result#ERROR|}
        print_error "操作失败: $error_msg"
        exit 1
    fi
}

# ===== 主入口 =====

echo "=========================================="
echo "    SOAR 管理员密码工具 v2.0 (bcrypt)"
echo "=========================================="

check_venv
check_database

case "${1:-}" in
    --random)
        print_info "生成随机密码..."
        do_reset ""
        ;;
    --set)
        if [ -z "${2:-}" ]; then
            print_error "请提供密码: $0 --set <password>"
            exit 1
        fi
        do_reset "$2"
        ;;
    --help|-h)
        show_usage
        exit 0
        ;;
    "")
        interactive_mode
        ;;
    *)
        print_error "未知参数: $1"
        show_usage
        exit 1
        ;;
esac
