#!/usr/bin/env python3
"""
自定义AuthProvider - 基于FastMCP的认证提供者
集成现有的数据库token验证系统
"""

from datetime import datetime
from typing import Optional, List
from starlette.requests import Request
from starlette.routing import BaseRoute, Route
from starlette.responses import JSONResponse

from fastmcp.server.auth import AuthProvider, AccessToken
from models import db_manager
from logger_config import logger


class SOARAuthProvider(AuthProvider):
    """
    SOAR自定义认证提供者
    基于URL参数中的token进行认证
    """

    def __init__(self, required_scopes: List[str] = None):
        self.required_scopes = required_scopes or []
        logger.info("SOARAuthProvider初始化完成")

    async def authenticate(self, request: Request) -> Optional[AccessToken]:
        """认证请求并返回访问令牌"""
        try:
            token_value = request.query_params.get('token')
            if not token_value:
                logger.debug("请求中缺少token参数")
                return None

            token_info = db_manager.get_token_by_value(token_value)
            if not token_info:
                logger.warning(f"无效的token: {token_value[:8]}...")
                return None

            is_valid = db_manager.verify_token(token_value)
            if not is_valid:
                logger.warning(f"Token验证失败: {token_value[:8]}...")
                return None

            logger.debug(f"Token验证成功: 用户={token_info['name']}")

            # 将用户信息存储到上下文
            try:
                from soar_mcp_server import set_current_user_info
                set_current_user_info(token_value, token_info)
            except Exception as e:
                logger.debug(f"存储用户信息到上下文失败: {e}")

            return AccessToken(
                token=token_value,
                scopes=self.required_scopes,
                expires_at=None,
                user_id=str(token_info['id']),
                username=token_info['name']
            )

        except Exception as e:
            logger.error(f"认证过程出错: {e}")
            return None

    def get_middleware(self):
        """返回认证中间件列表"""
        return []

    def get_routes(self, mcp_path: str, mcp_endpoint) -> List[BaseRoute]:
        """返回认证相关的路由"""
        routes = []

        async def protected_mcp_endpoint(request: Request):
            """受保护的MCP端点"""
            access_token = await self.authenticate(request)
            if not access_token:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "unauthorized",
                        "message": "Invalid or missing token. Please add ?token=your_token to the URL."
                    }
                )

            request.state.access_token = access_token
            request.state.user_id = access_token.user_id
            request.state.username = access_token.username

            try:
                from soar_mcp_server import set_current_user_info
                token_info = db_manager.get_token_by_value(access_token.token)
                set_current_user_info(access_token.token, token_info)
            except Exception as e:
                logger.debug(f"存储用户信息到上下文失败: {e}")

            if callable(mcp_endpoint):
                return await mcp_endpoint(request)
            else:
                return await mcp_endpoint(request.scope, request.receive, request._send)

        routes.append(
            Route(mcp_path, endpoint=protected_mcp_endpoint, methods=["GET", "POST"])
        )

        async def health_check(request: Request):
            """健康检查端点"""
            return JSONResponse({
                "status": "healthy",
                "auth_provider": "SOARAuthProvider",
                "timestamp": datetime.now().isoformat()
            })

        routes.append(Route("/health", endpoint=health_check, methods=["GET"]))
        return routes


# 创建全局认证提供者实例
soar_auth_provider = SOARAuthProvider()
