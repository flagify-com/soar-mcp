#!/usr/bin/env python3
"""
SOAR MCP服务器 - 使用FastMCP简化版本
"""

import json
import os
import asyncio
import threading
import time
from collections import OrderedDict
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Union

import httpx
from flask import Flask, jsonify, request, send_file
from threading import Thread

from fastmcp import FastMCP
from dotenv import load_dotenv
from version import __version__
from models import db_manager
from sync_service import PlaybookSyncService
from logger_config import logger
from auth_utils import jwt_required
from config_manager import config_manager

# 加载环境变量
load_dotenv()

# 创建FastMCP应用
mcp = FastMCP(
    name="SOAR MCP Server",
    version=__version__,
    instructions="SOAR (Security Orchestration, Automation and Response) 平台集成服务器，提供安全编排、自动化和响应功能。"
)


# ===== 有界执行记录存储 =====

class BoundedDict(OrderedDict):
    """有最大容量限制的有序字典，超出时淘汰最早的条目"""
    def __init__(self, max_size: int = 1000):
        super().__init__()
        self.max_size = max_size

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            self.popitem(last=False)

EXECUTIONS = BoundedDict(max_size=1000)


# ===== 请求上下文 - 使用 contextvars 支持异步 =====

_ctx_token = ContextVar('_ctx_token', default=None)
_ctx_token_info = ContextVar('_ctx_token_info', default=None)
_ctx_user_id = ContextVar('_ctx_user_id', default=None)
_ctx_username = ContextVar('_ctx_username', default=None)


def set_current_user_info(token: str, token_info: dict):
    """设置当前请求的用户信息到上下文"""
    _ctx_token.set(token)
    _ctx_token_info.set(token_info)
    _ctx_user_id.set(token_info.get('id') if token_info else None)
    _ctx_username.set(token_info.get('name') if token_info else None)


def get_current_user_info() -> dict:
    """获取当前请求的用户信息"""
    return {
        'token': _ctx_token.get(),
        'token_info': _ctx_token_info.get(),
        'user_id': _ctx_user_id.get(),
        'username': _ctx_username.get()
    }


def clear_current_user_info():
    """清理当前请求的用户信息"""
    _ctx_token.set(None)
    _ctx_token_info.set(None)
    _ctx_user_id.set(None)
    _ctx_username.set(None)


# ===== 审计日志 =====

def audit_mcp_access(action: str = "unknown", resource: str = None, parameters: dict = None) -> None:
    """
    记录MCP工具访问的审计日志。
    注意：此函数仅做审计记录，不做认证验证。
    """
    try:
        user_info = get_current_user_info()
        token_info = user_info['token_info']

        if not token_info:
            try:
                token = _ctx_token.get()
                if token:
                    token_info = db_manager.get_token_by_value(token)
            except Exception:
                pass

        db_manager.log_audit_event(
            action=action,
            resource=resource,
            parameters=parameters,
            result="success",
            token_info=token_info
        )
    except Exception as e:
        logger.error(f"记录审计日志异常: {e}")


# ===== 共享异步 HTTP 客户端 =====

_soar_http_client: Optional[httpx.AsyncClient] = None


async def get_soar_client() -> httpx.AsyncClient:
    """获取或创建共享的异步 SOAR API 客户端"""
    global _soar_http_client
    if _soar_http_client is None or _soar_http_client.is_closed:
        ssl_verify = config_manager.get_ssl_verify()
        timeout = config_manager.get_timeout()
        _soar_http_client = httpx.AsyncClient(
            verify=ssl_verify,
            timeout=float(timeout)
        )
    return _soar_http_client


# ===== ID转换工具函数 =====

def parse_playbook_id(playbook_id) -> int:
    """解析剧本ID，支持 int 和 str 格式"""
    if isinstance(playbook_id, int):
        return playbook_id
    elif isinstance(playbook_id, str):
        return int(playbook_id)
    else:
        raise ValueError(f"不支持的剧本ID格式: {type(playbook_id)} - {playbook_id}")


# ===== Flask 管理后台 =====

admin_app = Flask(__name__)


@admin_app.route('/login')
def login_page():
    """登录页面"""
    try:
        return send_file('templates/login.html')
    except FileNotFoundError:
        return jsonify({"error": "登录页面未找到"}), 404


@admin_app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """管理员登录"""
    try:
        data = request.get_json()
        if not data or 'adminPassword' not in data:
            return jsonify({"success": False, "error": "请提供管理员密码"}), 400

        admin_password = data['adminPassword'].strip()
        if not admin_password:
            return jsonify({"success": False, "error": "管理员密码不能为空"}), 400

        auth_manager = admin_app.auth_manager
        jwt_token = auth_manager.login_with_password(admin_password)

        if jwt_token:
            return jsonify({"success": True, "jwt": jwt_token, "message": "登录成功"})
        else:
            return jsonify({"success": False, "error": "密码无效，请检查后重试"}), 401

    except Exception as e:
        logger.error(f"管理员登录失败: {e}")
        return jsonify({"success": False, "error": "登录过程中发生错误"}), 500


@admin_app.route('/api/admin/verify', methods=['GET'])
def verify_token():
    """验证JWT Token"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"valid": False}), 401
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({"valid": False}), 401

        auth_manager = admin_app.auth_manager
        payload = auth_manager.verify_jwt(token)
        if payload:
            return jsonify({"valid": True, "user": payload})
        else:
            return jsonify({"valid": False}), 401
    except Exception as e:
        logger.error(f"Token验证失败: {e}")
        return jsonify({"valid": False}), 401


@admin_app.route('/admin')
def admin_page():
    """管理后台首页"""
    try:
        return send_file('templates/admin.html')
    except FileNotFoundError:
        return jsonify({"error": "管理页面未找到"}), 404


@admin_app.route('/static/<path:filename>')
def serve_static(filename):
    """提供静态文件服务"""
    try:
        return send_file(f'static/{filename}')
    except FileNotFoundError:
        return jsonify({"error": "文件未找到"}), 404


@admin_app.route('/api/admin/playbooks')
@jwt_required
def get_admin_playbooks():
    """获取所有剧本（管理界面）"""
    try:
        playbooks = db_manager.get_playbooks_admin()
        return jsonify({"success": True, "data": playbooks, "total": len(playbooks)})
    except Exception as e:
        logger.error(f"获取管理剧本列表失败: {e}")
        return jsonify({"success": False, "error": "获取剧本列表时发生内部错误"}), 500


@admin_app.route('/api/admin/playbooks/<string:playbook_id>')
@jwt_required
def get_playbook_detail(playbook_id):
    """获取单个剧本详情"""
    try:
        if playbook_id.startswith('id_'):
            playbook_id_int = int(playbook_id[3:])
        else:
            playbook_id_int = int(playbook_id)
        playbook = db_manager.get_playbook_by_id(playbook_id_int)
        if playbook:
            return jsonify({"success": True, "data": playbook})
        else:
            return jsonify({"success": False, "error": "剧本未找到"}), 404
    except Exception as e:
        logger.error(f"获取剧本详情失败: {e}")
        return jsonify({"success": False, "error": "获取剧本详情时发生内部错误"}), 500


@admin_app.route('/api/admin/playbooks/<string:playbook_id>/toggle', methods=['POST'])
@jwt_required
def toggle_playbook(playbook_id):
    """切换剧本启用状态"""
    try:
        if playbook_id.startswith('id_'):
            playbook_id_int = int(playbook_id[3:])
        else:
            playbook_id_int = int(playbook_id)
        data = request.get_json()
        enabled = data.get('enabled', True)
        success = db_manager.update_playbook_status(playbook_id_int, enabled)
        if success:
            return jsonify({"success": True, "message": f"剧本 {playbook_id} 已{'启用' if enabled else '禁用'}"})
        else:
            return jsonify({"success": False, "error": f"未找到剧本 {playbook_id}"}), 404
    except Exception as e:
        logger.error(f"切换剧本状态失败: {e}")
        return jsonify({"success": False, "error": "切换剧本状态时发生内部错误"}), 500


@admin_app.route('/api/admin/config', methods=['GET'])
@jwt_required
def get_system_config():
    """获取系统配置"""
    try:
        config = config_manager.get_soar_config()
        config_dict = config.model_dump()
        if config_dict.get('soar_api_token'):
            token = config_dict['soar_api_token']
            if len(token) > 10:
                config_dict['soar_api_token'] = token[:6] + '****' + token[-4:]
        return jsonify({"success": True, "data": config_dict})
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}")
        return jsonify({"success": False, "error": "获取配置时发生内部错误"}), 500


@admin_app.route('/api/admin/config', methods=['POST'])
@jwt_required
def update_system_config():
    """更新系统配置"""
    try:
        from models import SystemConfigData

        data = request.get_json()
        old_config = config_manager.get_soar_config()

        if 'soar_api_token' not in data:
            data['soar_api_token'] = old_config.soar_api_token

        try:
            config_data = SystemConfigData(**data)
        except Exception as e:
            return jsonify({"success": False, "error": f"配置数据格式错误: {e}"}), 400

        # 检查影响同步的字段变化
        sync_affecting_fields = []
        if old_config.soar_api_url != config_data.soar_api_url:
            sync_affecting_fields.append("API地址")
        if 'soar_api_token' in data and not data['soar_api_token'].startswith('***'):
            if old_config.soar_api_token != config_data.soar_api_token:
                sync_affecting_fields.append("API Token")
        if set(old_config.soar_labels or []) != set(config_data.soar_labels or []):
            sync_affecting_fields.append("标签配置")
        if old_config.soar_timeout != config_data.soar_timeout:
            sync_affecting_fields.append("超时设置")

        success = config_manager.update_soar_config(config_data)

        if success and sync_affecting_fields:
            logger.info(f"检测到影响同步的配置变化: {', '.join(sync_affecting_fields)}")

            def trigger_immediate_sync():
                try:
                    if not config_manager.is_first_run():
                        logger.sync_start(f"配置变化触发立即同步...")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            playbook_sync_service = PlaybookSyncService(db_manager)
                            result = loop.run_until_complete(playbook_sync_service.full_sync())
                            if "error" in result:
                                logger.sync_warning(f"配置变化触发的同步失败: {result['error']}")
                            else:
                                logger.sync_success("配置变化触发的同步完成!")
                        except Exception as e:
                            logger.sync_error(f"配置变化触发的同步异常: {e}")
                        finally:
                            loop.close()
                except Exception as e:
                    logger.error(f"触发立即同步失败: {e}")

            sync_thread = threading.Thread(target=trigger_immediate_sync, daemon=True)
            sync_thread.start()
            return jsonify({"success": True, "message": "系统配置已更新，正在触发数据同步..."})
        elif success:
            return jsonify({"success": True, "message": "系统配置已更新"})
        else:
            return jsonify({"success": False, "error": "配置更新失败"}), 500

    except Exception as e:
        logger.error(f"更新系统配置失败: {e}")
        return jsonify({"success": False, "error": "更新配置时发生内部错误"}), 500


@admin_app.route('/api/admin/config/validate', methods=['POST'])
@jwt_required
def validate_system_config():
    """验证系统配置"""
    try:
        config_data = None
        if request.is_json:
            data = request.get_json()
            if data:
                from models import SystemConfigData
                try:
                    config_data = SystemConfigData(**data)
                except Exception as e:
                    return jsonify({"success": False, "error": f"配置数据格式错误: {e}"}), 400
        validation_result = config_manager.validate_config(config_data)
        return jsonify({"success": True, "data": validation_result})
    except Exception as e:
        logger.error(f"验证系统配置失败: {e}")
        return jsonify({"success": False, "error": "验证配置时发生内部错误"}), 500


@admin_app.route('/api/admin/config/test', methods=['POST'])
@jwt_required
def test_connection():
    """测试API连接"""
    try:
        config_data = None
        if request.is_json:
            data = request.get_json()
            if data:
                from models import SystemConfigData
                try:
                    config_data = SystemConfigData(**data)
                except Exception as e:
                    return jsonify({"success": False, "error": f"配置数据格式错误: {e}"}), 400
        test_result = config_manager.test_connection(config_data)
        return jsonify({"success": True, "data": test_result})
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return jsonify({"success": False, "error": "测试连接时发生内部错误"}), 500


@admin_app.route('/api/admin/tokens', methods=['GET'])
@jwt_required
def get_tokens():
    """获取所有Token列表"""
    try:
        tokens = db_manager.get_user_tokens()
        return jsonify({"success": True, "data": tokens})
    except Exception as e:
        logger.error(f"获取Token列表失败: {e}")
        return jsonify({"success": False, "error": "获取Token列表时发生内部错误"}), 500


@admin_app.route('/api/admin/tokens', methods=['POST'])
@jwt_required
def create_token():
    """创建新Token"""
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({"success": False, "error": "请提供Token名称"}), 400
        name = data['name'].strip()
        expires_in_days = data.get('expires_in_days')
        if not name:
            return jsonify({"success": False, "error": "Token名称不能为空"}), 400
        token = db_manager.create_user_token(name, expires_in_days)
        if token:
            return jsonify({"success": True, "token": token, "message": "Token创建成功"})
        else:
            return jsonify({"success": False, "error": "Token创建失败"}), 500
    except Exception as e:
        logger.error(f"创建Token失败: {e}")
        return jsonify({"success": False, "error": "创建Token时发生内部错误"}), 500


@admin_app.route('/api/admin/tokens/<int:token_id>', methods=['DELETE'])
@jwt_required
def delete_token(token_id):
    """删除Token"""
    try:
        success = db_manager.delete_user_token(token_id)
        if success:
            return jsonify({"success": True, "message": "Token删除成功"})
        else:
            return jsonify({"success": False, "error": "Token删除失败或不存在"}), 404
    except Exception as e:
        logger.error(f"删除Token失败: {e}")
        return jsonify({"success": False, "error": "删除Token时发生内部错误"}), 500


@admin_app.route('/api/admin/tokens/<int:token_id>/toggle', methods=['POST'])
@jwt_required
def toggle_token_status(token_id):
    """切换Token启用状态"""
    try:
        data = request.get_json()
        if not data or 'is_active' not in data:
            return jsonify({"success": False, "error": "请提供is_active参数"}), 400
        is_active = data['is_active']
        success = db_manager.update_token_status(token_id, is_active)
        if success:
            return jsonify({"success": True, "message": f"Token已{'启用' if is_active else '禁用'}"})
        else:
            return jsonify({"success": False, "error": "Token状态更新失败或不存在"}), 404
    except Exception as e:
        logger.error(f"更新Token状态失败: {e}")
        return jsonify({"success": False, "error": "更新Token状态时发生内部错误"}), 500


@admin_app.route('/api/admin/stats', methods=['GET'])
@jwt_required
def get_system_stats():
    """获取系统统计信息"""
    try:
        playbooks_stats = db_manager.get_playbooks_stats()
        apps_stats = db_manager.get_apps_stats()
        stats = {**playbooks_stats, **apps_stats, "last_sync_time": db_manager.get_last_sync_time()}
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        return jsonify({"success": False, "error": "获取统计信息时发生内部错误"}), 500


def start_admin_server(port, host='127.0.0.1'):
    """启动管理后台服务器"""
    admin_app.run(host=host, port=port, debug=False, use_reloader=False)


# ===== MCP 工具定义 =====

@mcp.tool
def list_playbooks_quick(category: Optional[str] = None, limit: int = 100) -> str:
    """
    获取简洁的剧本列表 - 只包含基本信息(ID, name, displayName)

    Args:
        category: 按分类筛选剧本（可选）
        limit: 限制返回数量，默认100

    Returns:
        包含剧本列表的JSON字符串
    """
    audit_mcp_access(action="list_playbooks_quick", resource="soar://playbooks",
                     parameters={"category": category, "limit": limit})
    try:
        playbooks = db_manager.get_playbooks(category=category, limit=limit)
        result = {
            "total": len(playbooks),
            "playbooks": [{"id": p.id, "name": p.name, "displayName": p.display_name} for p in playbooks]
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"获取剧本列表失败: {str(e)}"}, ensure_ascii=False, indent=2)


@mcp.tool
def query_playbook_execution_params(playbook_id: Union[int, str]) -> str:
    """
    查询剧本执行参数 - 根据剧本ID获取执行所需的参数定义

    Args:
        playbook_id: 剧本ID，支持整数或字符串格式

    Returns:
        包含剧本参数定义的JSON字符串
    """
    audit_mcp_access(action="query_playbook_execution_params",
                     resource=f"soar://playbooks/{playbook_id}",
                     parameters={"playbook_id": playbook_id})
    try:
        playbook_id_int = parse_playbook_id(playbook_id)
        playbook = db_manager.get_playbook(playbook_id_int)
        if not playbook:
            return json.dumps({"error": f"未找到剧本 ID: {playbook_id}"}, ensure_ascii=False, indent=2)
        result = {
            "playbookId": playbook.id,
            "playbookName": playbook.name,
            "playbookDisplayName": playbook.display_name,
            "requiredParams": [
                {
                    "paramName": param.cef_column,
                    "paramDesc": param.cef_desc,
                    "paramType": param.value_type,
                    "required": True
                } for param in playbook.playbook_params
            ]
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"查询剧本参数失败: {str(e)}"}, ensure_ascii=False, indent=2)


@mcp.tool
async def execute_playbook(playbook_id: Union[int, str], parameters: Optional[dict] = None, event_id: int = 0) -> str:
    """
    执行SOAR剧本

    Args:
        playbook_id: 剧本ID，支持整数或字符串格式
        parameters: 执行参数字典（可选），格式 {"参数名": "参数值"}
        event_id: 事件ID（默认0）

    Returns:
        返回包含activity_id的JSON，用此ID查询状态和结果
    """
    audit_mcp_access(action="execute_playbook",
                     resource=f"soar://playbooks/{playbook_id}/execute",
                     parameters={"playbook_id": playbook_id, "parameters": parameters, "event_id": event_id})

    if parameters is None:
        parameters = {}

    try:
        playbook_id_int = parse_playbook_id(playbook_id)
        playbook = db_manager.get_playbook(playbook_id_int)
        if not playbook:
            return json.dumps({"error": f"未找到剧本 ID: {playbook_id}"}, ensure_ascii=False, indent=2)

        api_params = [{"key": key, "value": str(value)} for key, value in parameters.items()] if parameters else []

        api_request = {
            "eventId": event_id,
            "executorInstanceId": playbook_id_int,
            "executorInstanceType": "PLAYBOOK",
            "params": api_params
        }

        base_url = config_manager.get_api_url()
        api_token = config_manager.get_api_token()
        api_url = f"{base_url.rstrip('/')}/api/event/execution"
        headers = {'hg-token': api_token, 'Content-Type': 'application/json'}

        logger.info(f"调用SOAR API执行剧本 ID: {playbook_id_int}")

        client = await get_soar_client()
        response = await client.post(api_url, headers=headers, json=api_request)

        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.status_code}")

        api_result = response.json()
        if api_result.get('code') != 200:
            raise Exception(f"API返回错误: {api_result.get('message', '未知错误')}")

        activity_id = api_result.get('result')
        if not activity_id:
            raise Exception("API未返回活动ID")

        logger.info(f"剧本执行启动成功，活动ID: {activity_id}")
        execution_result = {"success": True, "activity_id": activity_id}
        EXECUTIONS[activity_id] = execution_result
        return json.dumps(execution_result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"执行剧本失败: {str(e)}",
            "playbookId": playbook_id,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def query_playbook_execution_status_by_activity_id(activity_id: str) -> str:
    """
    查询剧本执行状态

    Args:
        activity_id: 活动ID，从execute_playbook返回

    Returns:
        返回执行状态，当status为SUCCESS时可查询结果
    """
    if not activity_id or activity_id.strip() == "":
        return json.dumps({
            "success": False,
            "error": "activity_id 参数不能为空",
            "help": "请从 execute_playbook 返回结果的 activity_id 字段中获取"
        }, ensure_ascii=False, indent=2)

    audit_mcp_access(action="query_playbook_execution_status_by_activity_id",
                     resource=f"soar://executions/{activity_id}/status",
                     parameters={"activity_id": activity_id})

    try:
        base_url = config_manager.get_api_url()
        api_token = config_manager.get_api_token()
        api_url = f"{base_url.rstrip('/')}/odp/core/v1/api/activity/{activity_id}"
        headers = {'hg-token': api_token, 'Content-Type': 'application/json'}

        client = await get_soar_client()
        response = await client.get(api_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.status_code}")

        api_result = response.json()
        if api_result.get('code') != 200:
            raise Exception(f"API返回错误: {api_result.get('message', '未知错误')}")

        result_data = api_result.get('result', {})
        execution_status = result_data.get('executeStatus', 'UNKNOWN')

        status_result = {
            "success": True,
            "activityId": activity_id,
            "status": execution_status,
            "message": (
                f"执行已完成，请调用 query_playbook_execution_result_by_activity_id 查询详细结果"
                if execution_status == "SUCCESS"
                else f"执行进行中，请稍后再次查询"
            ),
            "queryTime": datetime.now().isoformat(),
            "details": {
                "executeStatus": execution_status,
                "eventId": result_data.get('eventId'),
                "executorInstanceId": result_data.get('executorInstanceId'),
                "executorInstanceName": result_data.get('executorInstanceName'),
                "createTime": result_data.get('createTime'),
                "updateTime": result_data.get('updateTime'),
            }
        }
        return json.dumps(status_result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"查询执行状态失败: {str(e)}",
            "activityId": activity_id,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2)


@mcp.tool
async def query_playbook_execution_result_by_activity_id(activity_id: str) -> str:
    """
    查询剧本执行详细结果

    Args:
        activity_id: 活动ID，从execute_playbook返回

    Returns:
        返回详细执行结果，建议先确认status为SUCCESS后调用
    """
    if not activity_id or activity_id.strip() == "":
        return json.dumps({
            "success": False,
            "error": "activity_id 参数不能为空",
            "help": "请从 execute_playbook 返回结果的 activity_id 字段中获取"
        }, ensure_ascii=False, indent=2)

    audit_mcp_access(action="query_playbook_execution_result_by_activity_id",
                     resource=f"soar://executions/{activity_id}/result",
                     parameters={"activity_id": activity_id})

    try:
        base_url = config_manager.get_api_url()
        api_token = config_manager.get_api_token()
        api_url = f"{base_url.rstrip('/')}/odp/core/v1/api/event/activity?activityId={activity_id}"
        headers = {'hg-token': api_token, 'Content-Type': 'application/json'}

        client = await get_soar_client()
        response = await client.get(api_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.status_code}")

        api_result = response.json()
        if api_result.get('code') != 200:
            raise Exception(f"API返回错误: {api_result.get('message', '未知错误')}")

        return json.dumps({
            "success": True,
            "activityId": activity_id,
            "queryTime": datetime.now().isoformat(),
            "executionResult": api_result
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"查询执行结果失败: {str(e)}",
            "activityId": activity_id,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2)


# ===== MCP 资源定义 =====

@mcp.resource("soar://applications")
def get_applications_resource() -> str:
    """获取SOAR应用资源"""
    audit_mcp_access(action="get_applications_resource", resource="soar://applications")
    try:
        apps = db_manager.get_apps(limit=10) if hasattr(db_manager, 'get_apps') else []
        return json.dumps([{
            "id": app.id, "name": app.name, "description": app.description,
            "version": app.version, "category": app.category
        } for app in apps], ensure_ascii=False, indent=2)
    except Exception:
        return json.dumps({"message": "应用资源暂不可用"}, ensure_ascii=False, indent=2)


@mcp.resource("soar://playbooks")
def get_playbooks_resource() -> str:
    """获取SOAR剧本资源"""
    audit_mcp_access(action="get_playbooks_resource", resource="soar://playbooks")
    try:
        playbooks = db_manager.get_playbooks(limit=10)
        return json.dumps([{
            "id": p.id, "name": p.name, "displayName": p.display_name,
            "category": p.playbook_category
        } for p in playbooks], ensure_ascii=False, indent=2)
    except Exception:
        return json.dumps({"message": "剧本资源暂不可用"}, ensure_ascii=False, indent=2)


@mcp.resource("soar://executions")
def get_executions_resource() -> str:
    """获取执行活动资源"""
    audit_mcp_access(action="get_executions_resource", resource="soar://executions")
    return json.dumps(list(EXECUTIONS.values()), ensure_ascii=False, indent=2)


# ===== 启动同步 =====

async def startup_sync():
    """服务器启动时执行初始同步"""
    try:
        skip_sync = os.getenv("SKIP_SYNC", "false").lower() == "true"
        if skip_sync:
            logger.sync_warning("跳过启动同步 (SKIP_SYNC=true)")
            return

        if config_manager.is_first_run():
            missing_configs = config_manager.get_missing_required_configs()
            logger.info("=" * 60)
            logger.info("检测到首次运行，跳过数据同步")
            logger.info(f"缺少必需配置: {', '.join(missing_configs)}")
            admin_port = int(os.getenv("ADMIN_PORT", str(int(os.getenv("MCP_PORT", os.getenv("SSE_PORT", "12345"))) + 1)))
            logger.info(f"请访问管理后台完成SOAR服务配置: http://127.0.0.1:{admin_port}/admin")
            logger.info("=" * 60)
            return

        logger.sync_start("执行启动同步...")
        playbook_sync_service = PlaybookSyncService(db_manager)
        playbook_result = await playbook_sync_service.full_sync()

        if "error" in playbook_result:
            logger.sync_warning(f"剧本同步失败: {playbook_result['error']}")
        else:
            logger.sync_success("剧本同步完成!")

    except Exception as e:
        logger.sync_error(f"启动同步异常: {e}")


class PeriodicSyncService:
    """定时同步服务"""

    def __init__(self):
        self.sync_thread = None
        self.stop_event = None

    def start_periodic_sync(self):
        """启动定时同步服务"""
        try:
            self.stop_event = threading.Event()
            self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
            self.sync_thread.start()
            logger.info("定时同步服务已启动")
        except Exception as e:
            logger.error(f"启动定时同步服务失败: {e}")

    def _sync_worker(self):
        """同步工作线程（使用持久化事件循环）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        last_sync_time = time.time()
        current_interval = None

        try:
            while not self.stop_event.is_set():
                try:
                    sync_interval = config_manager.get('sync_interval', 14400)

                    if current_interval != sync_interval:
                        current_interval = sync_interval
                        logger.info(f"同步周期: {sync_interval}秒 ({sync_interval // 3600}小时)")

                    current_time = time.time()
                    if current_time - last_sync_time >= sync_interval:
                        logger.sync_start("执行定时同步...")
                        loop.run_until_complete(self._perform_sync())
                        last_sync_time = current_time
                        logger.info(f"下次同步将在 {sync_interval} 秒后执行")

                    self.stop_event.wait(timeout=60)

                except Exception as e:
                    logger.sync_error(f"定时同步异常: {e}")
                    self.stop_event.wait(timeout=60)
        finally:
            loop.close()

    async def _perform_sync(self):
        """执行同步操作"""
        try:
            if config_manager.is_first_run():
                logger.sync_warning("定时同步暂停：缺少必需配置")
                return

            playbook_sync_service = PlaybookSyncService(db_manager)
            playbook_result = await playbook_sync_service.full_sync()

            if "error" in playbook_result:
                logger.sync_warning(f"剧本同步失败: {playbook_result['error']}")
            else:
                logger.sync_success("剧本定时同步完成!")
        except Exception as e:
            logger.sync_error(f"定时同步异常: {e}")

    def stop(self):
        """停止定时同步服务"""
        if self.stop_event:
            self.stop_event.set()
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5)
        logger.info("定时同步服务已停止")


periodic_sync_service = PeriodicSyncService()


# ===== 入口点 =====

if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", os.getenv("SSE_PORT", "12345")))
    admin_port = int(os.getenv("ADMIN_PORT", str(port + 1)))
    bind_host = os.getenv("BIND_HOST", "127.0.0.1")

    logger.server_info(f"启动 SOAR MCP 服务器 v{__version__}")
    logger.info(f"📊 MCP服务: http://{bind_host}:{port}/mcp")
    logger.info(f"🎛️  管理后台: http://{bind_host}:{admin_port}/admin")

    # 初始化
    logger.database_info("初始化数据库...")
    db_manager.init_db()

    logger.info("初始化系统配置...")
    config_manager.init()

    logger.info("初始化认证系统...")
    from auth_utils import create_auth_manager
    auth_manager = create_auth_manager()
    admin_password = auth_manager.init_admin_password()
    admin_app.auth_manager = auth_manager

    # 同步
    logger.info("启动同步任务...")
    asyncio.run(startup_sync())

    logger.info("启动定时同步服务...")
    periodic_sync_service.start_periodic_sync()

    # 启动管理后台
    logger.info(f"启动管理后台服务器 ({bind_host}:{admin_port})...")
    admin_thread = Thread(target=start_admin_server, args=(admin_port, bind_host), daemon=True)
    admin_thread.start()

    # 启动 MCP 服务器
    logger.server_info("启动MCP服务器...")

    try:
        def print_startup_info():
            time.sleep(2)
            logger.info("")
            logger.info("=" * 80)
            logger.info("🚀 服务器启动完成!")
            logger.info(f"📊 MCP服务: http://{bind_host}:{port}/mcp (带token参数)")
            logger.info(f"🎛️  管理后台: http://{bind_host}:{admin_port}/admin")
            logger.info("=" * 80)
            if admin_password:
                print(f"\n{'=' * 60}")
                print(f"  🔑 管理员初始密码: {admin_password}")
                print(f"  ⚠️  请妥善保管，此密码不会再次显示！")
                print(f"{'=' * 60}\n")
            else:
                print("  🔑 管理员密码已存在，如需重置请运行 reset_admin_password.sh")

        startup_thread = threading.Thread(target=print_startup_info, daemon=True)
        startup_thread.start()

        logger.info("🔐 认证系统已就绪")
        mcp.run(
            transport="streamable-http",
            host=bind_host,
            port=port,
            stateless_http=True,
            path="/mcp",
        )
    except KeyboardInterrupt:
        logger.info("服务器已停止")
