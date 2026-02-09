#!/usr/bin/env python3
"""
Bearer Token 认证测试套件

测试 SOAR MCP Server 的双模式 Token 认证：
1. HTTP Bearer Token (Authorization: Bearer <token>)
2. URL 查询参数 (?token=<token>)

使用方法:
    # 运行全部测试（需要服务器运行中）
    python tests/test_bearer_auth.py

    # 指定服务器地址和端口
    python tests/test_bearer_auth.py --host 127.0.0.1 --port 12345

    # 指定已有的Token
    python tests/test_bearer_auth.py --token <your_token>

    # 只运行单元测试（不需要服务器）
    python tests/test_bearer_auth.py --unit-only
"""

import sys
import os
import json
import argparse
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# 将项目根目录添加到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ========== 单元测试 ==========

class TestSOARAuthProviderUnit(unittest.TestCase):
    """SOARAuthProvider 单元测试（不需要服务器运行）"""

    def setUp(self):
        """初始化测试环境"""
        self.valid_token = "test_valid_token_abc123"
        self.invalid_token = "test_invalid_token_xyz"
        self.expired_token = "test_expired_token_999"
        self.token_info = {
            "id": 1,
            "name": "test-token",
            "token": self.valid_token,
            "is_active": True,
            "usage_count": 5,
            "created_at": "2025-01-01T00:00:00",
            "expires_at": None,
            "last_used_at": None,
        }

    @patch("auth_provider.db_manager")
    def test_verify_valid_token(self, mock_db_manager):
        """测试验证有效Token"""
        from auth_provider import SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = self.token_info
        mock_db_manager.verify_token.return_value = True

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(self.valid_token))

        self.assertIsNotNone(result)
        self.assertEqual(result.token, self.valid_token)
        self.assertEqual(result.client_id, "1")
        mock_db_manager.get_token_by_value.assert_called_once_with(self.valid_token)
        mock_db_manager.verify_token.assert_called_once_with(self.valid_token)

    @patch("auth_provider.db_manager")
    def test_verify_invalid_token(self, mock_db_manager):
        """测试验证无效Token"""
        from auth_provider import SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = None

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(self.invalid_token))

        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_verify_expired_token(self, mock_db_manager):
        """测试验证过期Token"""
        from auth_provider import SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = self.token_info
        mock_db_manager.verify_token.return_value = False

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(self.expired_token))

        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_verify_empty_token(self, mock_db_manager):
        """测试验证空Token"""
        from auth_provider import SOARAuthProvider

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(""))

        self.assertIsNone(result)
        mock_db_manager.get_token_by_value.assert_not_called()

    @patch("auth_provider.db_manager")
    def test_verify_none_token(self, mock_db_manager):
        """测试验证None Token"""
        from auth_provider import SOARAuthProvider

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(None))

        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_verify_token_db_exception(self, mock_db_manager):
        """测试数据库异常时的Token验证"""
        from auth_provider import SOARAuthProvider

        mock_db_manager.get_token_by_value.side_effect = Exception("DB connection error")

        provider = SOARAuthProvider()
        result = asyncio.run(provider.verify_token(self.valid_token))

        self.assertIsNone(result)

    def test_provider_initialization(self):
        """测试Provider初始化"""
        from auth_provider import SOARAuthProvider

        provider = SOARAuthProvider()
        self.assertEqual(provider.required_scopes, [])

        provider_with_scopes = SOARAuthProvider(required_scopes=["read", "write"])
        self.assertEqual(provider_with_scopes.required_scopes, ["read", "write"])

    def test_get_middleware(self):
        """测试中间件配置"""
        from auth_provider import SOARAuthProvider

        provider = SOARAuthProvider()
        middleware = provider.get_middleware()

        self.assertIsInstance(middleware, list)
        self.assertEqual(len(middleware), 2)  # AuthenticationMiddleware + AuthContextMiddleware


class TestBearerOrQueryAuthBackendUnit(unittest.TestCase):
    """BearerOrQueryAuthBackend 单元测试"""

    def _make_mock_conn(self, headers=None, query_params=None):
        """创建模拟的HTTP连接"""
        conn = MagicMock()
        conn.headers = headers or {}
        conn.query_params = query_params or {}
        return conn

    @patch("auth_provider.db_manager")
    def test_bearer_token_extraction(self, mock_db_manager):
        """测试从 Authorization: Bearer 头提取Token"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = {
            "id": 1, "name": "test", "token": "abc123",
            "is_active": True, "usage_count": 0,
            "created_at": None, "expires_at": None, "last_used_at": None,
        }
        mock_db_manager.verify_token.return_value = True

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        conn = self._make_mock_conn(
            headers={"authorization": "Bearer abc123"}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNotNone(result)
        credentials, user = result
        self.assertIn("abc123", user.access_token.token)

    @patch("auth_provider.db_manager")
    def test_query_param_token_extraction(self, mock_db_manager):
        """测试从 URL 查询参数提取Token"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = {
            "id": 2, "name": "test-query", "token": "query_token_456",
            "is_active": True, "usage_count": 0,
            "created_at": None, "expires_at": None, "last_used_at": None,
        }
        mock_db_manager.verify_token.return_value = True

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        conn = self._make_mock_conn(
            headers={},
            query_params={"token": "query_token_456"}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNotNone(result)
        credentials, user = result
        self.assertEqual(user.access_token.token, "query_token_456")

    @patch("auth_provider.db_manager")
    def test_bearer_takes_priority_over_query(self, mock_db_manager):
        """测试 Bearer 头优先于 URL 查询参数"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = {
            "id": 1, "name": "bearer-token", "token": "bearer_token_111",
            "is_active": True, "usage_count": 0,
            "created_at": None, "expires_at": None, "last_used_at": None,
        }
        mock_db_manager.verify_token.return_value = True

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        # 同时提供 Bearer 和 query param
        conn = self._make_mock_conn(
            headers={"authorization": "Bearer bearer_token_111"},
            query_params={"token": "query_token_222"}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNotNone(result)
        credentials, user = result
        # 应该使用 Bearer 头中的 token
        self.assertEqual(user.access_token.token, "bearer_token_111")

    def test_no_token_provided(self, ):
        """测试未提供任何Token"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        conn = self._make_mock_conn(headers={}, query_params={})

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_invalid_bearer_format(self, mock_db_manager):
        """测试无效的 Authorization 头格式（不是 Bearer）"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        # Basic auth 格式，不是 Bearer
        conn = self._make_mock_conn(
            headers={"authorization": "Basic dXNlcjpwYXNz"},
            query_params={}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_invalid_token_returns_none(self, mock_db_manager):
        """测试无效Token返回None"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = None

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        conn = self._make_mock_conn(
            headers={"authorization": "Bearer invalid_token_xyz"}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNone(result)

    @patch("auth_provider.db_manager")
    def test_case_insensitive_bearer(self, mock_db_manager):
        """测试 Authorization 头大小写不敏感"""
        from auth_provider import BearerOrQueryAuthBackend, SOARAuthProvider

        mock_db_manager.get_token_by_value.return_value = {
            "id": 1, "name": "test", "token": "case_test_token",
            "is_active": True, "usage_count": 0,
            "created_at": None, "expires_at": None, "last_used_at": None,
        }
        mock_db_manager.verify_token.return_value = True

        provider = SOARAuthProvider()
        backend = BearerOrQueryAuthBackend(provider)

        # 大小写混合的 Bearer
        conn = self._make_mock_conn(
            headers={"authorization": "BEARER case_test_token"}
        )

        result = asyncio.run(backend.authenticate(conn))
        self.assertIsNotNone(result)


# ========== 集成测试（需要服务器运行） ==========

class TestBearerAuthIntegration:
    """集成测试：需要 MCP Server 正在运行"""

    def __init__(self, host: str, port: int, admin_port: int, token: str = None):
        self.host = host
        self.port = port
        self.admin_port = admin_port
        self.base_url = f"http://{host}:{port}"
        self.admin_url = f"http://{host}:{admin_port}"
        self.token = token
        self.results = {"passed": 0, "failed": 0, "tests": []}

    def _record(self, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        emoji = "✅" if passed else "❌"
        print(f"  {emoji} {name}: {detail}" if detail else f"  {emoji} {name}")
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
        self.results["tests"].append({"name": name, "passed": passed, "detail": detail})

    def run_all(self):
        """运行全部集成测试"""
        import requests

        print("\n" + "=" * 70)
        print("🧪 Bearer Token 认证集成测试")
        print(f"   MCP Server: {self.base_url}")
        print(f"   Admin:      {self.admin_url}")
        print("=" * 70)

        # 如果没有提供 Token，先通过 admin API 创建一个
        if not self.token:
            print("\n⚠️  未提供Token，请使用 --token 参数指定一个有效Token")
            print("   或先在管理后台创建Token后提供")
            return

        print(f"\n📌 使用Token: {self.token[:8]}...{self.token[-4:]}")

        # 1. 测试 Bearer Token 认证
        print("\n--- 1. Bearer Token 认证测试 ---")
        self._test_bearer_mcp_endpoint(requests)

        # 2. 测试 URL 查询参数认证
        print("\n--- 2. URL 查询参数认证测试 ---")
        self._test_query_param_mcp_endpoint(requests)

        # 3. 测试无认证
        print("\n--- 3. 无认证测试 ---")
        self._test_no_auth_rejected(requests)

        # 4. 测试无效Token
        print("\n--- 4. 无效Token测试 ---")
        self._test_invalid_token_rejected(requests)

        # 5. 测试 Bearer 格式错误
        print("\n--- 5. 错误格式测试 ---")
        self._test_malformed_bearer(requests)

        # 打印总结
        print("\n" + "=" * 70)
        total = self.results["passed"] + self.results["failed"]
        print(f"📊 测试完成: {self.results['passed']}/{total} 通过")
        if self.results["failed"] > 0:
            print(f"   ❌ {self.results['failed']} 个测试失败")
        else:
            print("   🎉 全部测试通过!")
        print("=" * 70)

    def _test_bearer_mcp_endpoint(self, requests):
        """测试 Bearer Token 访问 MCP 端点"""
        try:
            # POST 请求 MCP endpoint with Bearer token
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            # 发送 MCP initialize 请求
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-bearer-auth", "version": "1.0.0"}
                }
            }
            resp = requests.post(
                f"{self.base_url}/mcp",
                headers=headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                self._record("Bearer Token POST /mcp", True, f"status={resp.status_code}")
            else:
                self._record("Bearer Token POST /mcp", False, f"status={resp.status_code}, body={resp.text[:200]}")
        except Exception as e:
            self._record("Bearer Token POST /mcp", False, f"异常: {e}")

    def _test_query_param_mcp_endpoint(self, requests):
        """测试 URL 查询参数访问 MCP 端点"""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-query-auth", "version": "1.0.0"}
                }
            }
            resp = requests.post(
                f"{self.base_url}/mcp?token={self.token}",
                headers=headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                self._record("Query Param POST /mcp?token=xxx", True, f"status={resp.status_code}")
            else:
                self._record("Query Param POST /mcp?token=xxx", False, f"status={resp.status_code}, body={resp.text[:200]}")
        except Exception as e:
            self._record("Query Param POST /mcp?token=xxx", False, f"异常: {e}")

    def _test_no_auth_rejected(self, requests):
        """测试无认证请求被拒绝"""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-no-auth", "version": "1.0.0"}
                }
            }
            resp = requests.post(
                f"{self.base_url}/mcp",
                headers=headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 401:
                self._record("无认证 POST /mcp → 401", True, f"正确拒绝，status={resp.status_code}")
            else:
                self._record("无认证 POST /mcp → 401", False, f"预期401，实际status={resp.status_code}")
        except Exception as e:
            self._record("无认证 POST /mcp → 401", False, f"异常: {e}")

    def _test_invalid_token_rejected(self, requests):
        """测试无效Token被拒绝"""
        try:
            # Bearer 无效 Token
            headers = {
                "Authorization": "Bearer totally_invalid_token_12345",
                "Content-Type": "application/json",
            }
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-invalid", "version": "1.0.0"}
                }
            }
            resp = requests.post(
                f"{self.base_url}/mcp",
                headers=headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 401:
                self._record("无效Bearer Token → 401", True, f"正确拒绝")
            else:
                self._record("无效Bearer Token → 401", False, f"预期401，实际status={resp.status_code}")
        except Exception as e:
            self._record("无效Bearer Token → 401", False, f"异常: {e}")

        try:
            # URL 参数无效 Token
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-invalid-query", "version": "1.0.0"}
                }
            }
            resp = requests.post(
                f"{self.base_url}/mcp?token=totally_invalid_query_token",
                headers=headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 401:
                self._record("无效Query Token → 401", True, f"正确拒绝")
            else:
                self._record("无效Query Token → 401", False, f"预期401，实际status={resp.status_code}")
        except Exception as e:
            self._record("无效Query Token → 401", False, f"异常: {e}")

    def _test_malformed_bearer(self, requests):
        """测试错误格式的 Authorization 头"""
        test_cases = [
            ("Basic dXNlcjpwYXNz", "Basic认证格式"),
            ("bearer", "缺少Token值"),
            ("Token abc123", "错误前缀"),
        ]
        for auth_value, desc in test_cases:
            try:
                headers = {
                    "Authorization": auth_value,
                    "Content-Type": "application/json",
                }
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-malformed", "version": "1.0.0"}
                    }
                }
                resp = requests.post(
                    f"{self.base_url}/mcp",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                if resp.status_code == 401:
                    self._record(f"格式错误({desc}) → 401", True, "正确拒绝")
                else:
                    self._record(f"格式错误({desc}) → 401", False, f"预期401，实际={resp.status_code}")
            except Exception as e:
                self._record(f"格式错误({desc}) → 401", False, f"异常: {e}")


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(description="Bearer Token 认证测试套件")
    parser.add_argument("--host", default="127.0.0.1", help="MCP Server 地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=12345, help="MCP Server 端口 (默认 12345)")
    parser.add_argument("--admin-port", type=int, default=12346, help="Admin 端口 (默认 12346)")
    parser.add_argument("--token", default=None, help="用于测试的有效Token")
    parser.add_argument("--unit-only", action="store_true", help="只运行单元测试（不需要服务器）")

    args = parser.parse_args()

    # 运行单元测试
    print("\n" + "=" * 70)
    print("🧪 运行单元测试...")
    print("=" * 70 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSOARAuthProviderUnit))
    suite.addTests(loader.loadTestsFromTestCase(TestBearerOrQueryAuthBackendUnit))

    runner = unittest.TextTestRunner(verbosity=2)
    unit_result = runner.run(suite)

    if args.unit_only:
        sys.exit(0 if unit_result.wasSuccessful() else 1)

    # 运行集成测试
    integration = TestBearerAuthIntegration(
        host=args.host,
        port=args.port,
        admin_port=args.admin_port,
        token=args.token,
    )
    integration.run_all()

    # 总结
    if not unit_result.wasSuccessful() or integration.results.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
