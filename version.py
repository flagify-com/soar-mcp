#!/usr/bin/env python3
"""
SOAR MCP Server 版本管理
"""

__version__ = "1.0.1"
__version_info__ = (1, 0, 1)

# 版本说明
VERSION_NOTES = {
    "1.0.0": "首个稳定版本，支持SOAR剧本执行和MCP集成",
    "1.0.1": "修复统计页面最后同步时间显示问题和时区处理问题"
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