#!/usr/bin/env python3
"""
自定义AuthProvider - 基于FastMCP的认证提供者
支持双模式认证：HTTP Bearer Token 和 URL查询参数Token
"""

from datetime import datetime
from typing import Optional, List, Any

from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.routing import Route

from fastmcp.server.auth import AccessToken, AuthProvider
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import (
    AuthenticatedUser,
    RequireAuthMiddleware,
)
from models import db_manager
from logger_config import logger


class BearerOrQueryAuthBackend(AuthenticationBackend):
    """
    双模式认证后端：优先检查 Authorization: Bearer <token>，
    如果没有则 fallback 到 URL 查询参数 ?token=<token>。

    认证优先级：
    1. HTTP Header: Authorization: Bearer <token>  （推荐，更安全）
    2. URL Query:   ?token=<token>                  （兼容模式）
    """

    def __init__(self, token_verifier: "SOARAuthProvider"):
        self.token_verifier = token_verifier

    async def authenticate(self, conn: HTTPConnection):
        token_value = None
        auth_method = None

        # 优先级1: 检查 Authorization: Bearer <token> 头
        auth_header = next(
            (conn.headers.get(key) for key in conn.headers if key.lower() == "authorization"),
            None,
        )
        if auth_header and auth_header.lower().startswith("bearer "):
            token_value = auth_header[7:]  # 去掉 "Bearer " 前缀
            auth_method = "bearer"

        # 优先级2: 检查 URL 查询参数 ?token=<token>
        if not token_value:
            token_value = conn.query_params.get("token")
            if token_value:
                auth_method = "query_param"

        if not token_value:
            return None

        # 使用 verify_token 验证
        access_token = await self.token_verifier.verify_token(token_value)
        if not access_token:
            return None

        logger.debug(f"认证成功 [method={auth_method}]: client_id={access_token.client_id}")
        return AuthCredentials(access_token.scopes), AuthenticatedUser(access_token)


class SOARAuthProvider(AuthProvider):
    """
    SOAR自定义认证提供者

    支持双模式Token认证：
    - HTTP Bearer Token: Authorization: Bearer <token>  (推荐)
    - URL查询参数:       ?token=<token>                  (兼容)

    两种方式使用同一套Token体系，后端验证逻辑完全复用。
    """

    def __init__(self, required_scopes: List[str] = None):
        super().__init__(base_url=None, required_scopes=required_scopes or [])
        logger.info("SOARAuthProvider初始化完成 (支持Bearer Token + URL参数双模式认证)")

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        验证Token并返回AccessToken。

        此方法被 BearerOrQueryAuthBackend 调用，
        无论Token来自 Bearer header 还是 URL 参数都走这个验证逻辑。
        """
        try:
            if not token:
                return None

            # 从数据库查找Token信息
            token_info = db_manager.get_token_by_value(token)
            if not token_info:
                logger.warning(f"无效的token: {token[:8]}...")
                return None

            # 验证Token有效性（同时更新使用统计）
            is_valid = db_manager.verify_token(token)
            if not is_valid:
                logger.warning(f"Token验证失败: {token[:8]}...")
                return None

            logger.debug(f"Token验证成功: 用户={token_info['name']}")

            # 将用户信息存储到请求上下文
            try:
                from soar_mcp_server import set_current_user_info
                set_current_user_info(token, token_info)
            except Exception as e:
                logger.debug(f"存储用户信息到上下文失败: {e}")

            return AccessToken(
                token=token,
                client_id=str(token_info['id']),
                scopes=self.required_scopes,
                expires_at=None,
            )

        except Exception as e:
            logger.error(f"认证过程出错: {e}")
            return None

    def get_middleware(self) -> list:
        """返回认证中间件列表，使用自定义的双模式认证后端"""
        return [
            Middleware(
                AuthenticationMiddleware,
                backend=BearerOrQueryAuthBackend(self),
            ),
            Middleware(AuthContextMiddleware),
        ]

    def get_routes(
        self,
        mcp_path: str = None,
        mcp_endpoint: Any = None,
    ) -> List[Route]:
        """返回认证相关的路由"""
        routes = []

        # 添加受保护的MCP端点
        if mcp_path and mcp_endpoint:
            resource_metadata_url = self._get_resource_url(
                "/.well-known/oauth-protected-resource"
            )
            routes.append(
                Route(
                    mcp_path,
                    endpoint=RequireAuthMiddleware(
                        mcp_endpoint, self.required_scopes, resource_metadata_url
                    ),
                )
            )

        return routes


# 创建全局认证提供者实例
soar_auth_provider = SOARAuthProvider()
