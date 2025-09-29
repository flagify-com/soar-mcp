#!/bin/bash

# SOAR MCP Server 代码汇总生成脚本
# 生成包含所有源代码的单一文件

echo "开始生成 SOAR MCP Server 代码汇总文件..."

# 输出文件
OUTPUT_FILE="docs/完整源代码汇总.txt"

# 创建docs目录（如果不存在）
mkdir -p docs

# 清空输出文件
> "$OUTPUT_FILE"

# 添加文件头
cat << 'EOF' >> "$OUTPUT_FILE"
================================================================================
                    SOAR MCP Server 完整源代码汇总
================================================================================

项目名称: SOAR 安全编排自动化响应 MCP 服务器
英文名称: SOAR Security Orchestration Automation Response MCP Server
版本号: V1.0
生成时间: $(date '+%Y-%m-%d %H:%M:%S')

本文件包含项目的所有Python源代码文件，按照文件重要性排序。
每个文件都有明确的分隔符和文件信息标注。

================================================================================

EOF

# 定义源代码文件列表（按重要性排序）
SOURCE_FILES=(
    "soar_mcp_server.py"
    "models.py"
    "sync_service.py"
    "auth_utils.py"
    "auth_provider.py"
    "config_manager.py"
    "logger_config.py"
    "version.py"
)

# 测试文件列表
TEST_FILES=(
    "tests/mcp_soar_client.py"
    "tests/test_new_mcp_tools.py"
    "tests/test_new_playbook_tools.py"
    "tests/test_unified_execute_playbook.py"
    "tests/test_real_api.py"
    "tests/test_admin_api.py"
    "tests/test_execute_api.py"
    "tests/test_playbook_sync.py"
    "tests/test_concurrent_sync.py"
    "tests/test_playbook_params.py"
    "tests/test_tools_manual.py"
    "tests/test_tools_direct.py"
    "tests/simple_test.py"
)

# 处理核心源代码文件
echo "正在处理核心源代码文件..."
echo "" >> "$OUTPUT_FILE"
echo "【核心源代码文件】" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for file in "${SOURCE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "处理文件: $file"

        # 获取文件信息
        FILE_SIZE=$(wc -l < "$file" 2>/dev/null || echo "0")
        FILE_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file" 2>/dev/null || date)

        cat << EOF >> "$OUTPUT_FILE"
################################################################################
# 文件: $file
# 行数: ${FILE_SIZE} 行
# 修改时间: ${FILE_DATE}
# 描述: $(head -5 "$file" | grep -E '^#|"""' | head -1 | sed 's/^[#"]*\s*//')
################################################################################

EOF

        # 添加文件内容
        cat "$file" >> "$OUTPUT_FILE"

        cat << 'EOF' >> "$OUTPUT_FILE"


################################################################################
# 文件结束
################################################################################


EOF
    else
        echo "警告: 文件 $file 不存在"
    fi
done

# 处理测试文件
echo "正在处理测试文件..."
echo "" >> "$OUTPUT_FILE"
echo "【测试代码文件】" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "处理文件: $file"

        # 获取文件信息
        FILE_SIZE=$(wc -l < "$file" 2>/dev/null || echo "0")
        FILE_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file" 2>/dev/null || date)

        cat << EOF >> "$OUTPUT_FILE"
################################################################################
# 测试文件: $file
# 行数: ${FILE_SIZE} 行
# 修改时间: ${FILE_DATE}
# 描述: $(head -10 "$file" | grep -E '^#|"""' | head -1 | sed 's/^[#"]*\s*//')
################################################################################

EOF

        # 添加文件内容
        cat "$file" >> "$OUTPUT_FILE"

        cat << 'EOF' >> "$OUTPUT_FILE"


################################################################################
# 测试文件结束
################################################################################


EOF
    else
        echo "警告: 测试文件 $file 不存在"
    fi
done

# 添加配置文件
echo "正在处理配置文件..."
CONFIG_FILES=(
    "requirements.txt"
    ".env.example"
    "CLAUDE.md"
)

echo "" >> "$OUTPUT_FILE"
echo "【配置文件】" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "处理配置文件: $file"

        cat << EOF >> "$OUTPUT_FILE"
################################################################################
# 配置文件: $file
################################################################################

EOF

        cat "$file" >> "$OUTPUT_FILE"

        cat << 'EOF' >> "$OUTPUT_FILE"


################################################################################
# 配置文件结束
################################################################################


EOF
    fi
done

# 添加统计信息
echo "正在生成统计信息..."
TOTAL_LINES=$(find . -name "*.py" -not -path "./venv/*" -exec wc -l {} + | tail -1 | awk '{print $1}')
TOTAL_FILES=$(find . -name "*.py" -not -path "./venv/*" | wc -l)

cat << EOF >> "$OUTPUT_FILE"
================================================================================
                               代码统计信息
================================================================================

项目代码统计:
- Python文件总数: ${TOTAL_FILES} 个
- 代码总行数: ${TOTAL_LINES} 行
- 核心模块: ${#SOURCE_FILES[@]} 个
- 测试文件: ${#TEST_FILES[@]} 个
- 配置文件: ${#CONFIG_FILES[@]} 个

文件分布:
$(find . -name "*.py" -not -path "./venv/*" -exec wc -l {} + | sort -nr | head -10)

生成完成时间: $(date '+%Y-%m-%d %H:%M:%S')

================================================================================
                                文件结束
================================================================================
EOF

# 获取生成文件的大小
OUTPUT_SIZE=$(wc -l < "$OUTPUT_FILE")
OUTPUT_SIZE_KB=$(du -k "$OUTPUT_FILE" | cut -f1)

echo ""
echo "================================"
echo "代码汇总文件生成完成！"
echo "================================"
echo "输出文件: $OUTPUT_FILE"
echo "文件行数: $OUTPUT_SIZE 行"
echo "文件大小: ${OUTPUT_SIZE_KB} KB"
echo "包含文件: $((${#SOURCE_FILES[@]} + ${#TEST_FILES[@]} + ${#CONFIG_FILES[@]})) 个"
echo "================================"
echo ""
echo "可以使用以下命令查看文件："
echo "  cat '$OUTPUT_FILE'"
echo "  less '$OUTPUT_FILE'"
echo "  head -50 '$OUTPUT_FILE'"
echo ""