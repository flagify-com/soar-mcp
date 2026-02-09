#!/usr/bin/env python3
"""
SOAR MCP Server 版本管理
"""

__version__ = "1.3.0"
__version_info__ = (1, 3, 0)

# 版本说明
VERSION_NOTES = {
    "1.0.0": "首个稳定版本，支持SOAR剧本执行和MCP集成",
    "1.0.1": "修复统计页面最后同步时间显示问题和时区处理问题",
    "1.0.2": "统一MCP工具名称，修复文档和代码中的命名不一致问题",
    "1.0.3": "优化MCP工具命名，增强AI可理解性和语义明确性",
    "1.0.4": "优化剧本标签管理逻辑，支持空标签同步所有剧本，适配社区免费版",
    "1.1.0": "安全加固：bcrypt密码哈希、JWT密钥持久化、移除敏感信息日志泄露",
    "1.1.1": "安全加固：SSL验证可配置(默认开启)、服务默认绑定127.0.0.1、修复配置缓存竞态、统一环境变量",
    "1.2.0": "架构改进：异步MCP工具(httpx)、contextvars替代threading.local、有界执行记录、DB session上下文管理器、清理冗余代码",
    "1.2.1": "代码质量：修复auth_provider模块引用、健康检查、日志轮转、清理未使用依赖",
    "1.2.2": "密码脚本升级bcrypt v2.0、README/CLAUDE.md文档全面更新适配新架构",
    "1.3.0": "项目结构优化、文档整理归档、清理无用文件、目录规范化"
}

def get_version():
    """获取当前版本号"""
    return __version__

def get_version_info():
    """获取版本信息元组"""
    return __version_info__

def get_version_string():
    """获取详细版本字符串"""
    return f"SOAR MCP Server v{__version__}"