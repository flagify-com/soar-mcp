#!/usr/bin/env python3
"""
认证工具模块
处理密码认证、JWT认证等功能
"""

import secrets
import string
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, jsonify, current_app

from models import db_manager
from logger_config import logger


class AuthManager:
    """认证管理器"""

    def __init__(self, jwt_secret_key: str = None):
        if jwt_secret_key:
            self.jwt_secret_key = jwt_secret_key
        else:
            # 从数据库加载持久化的 JWT 密钥，不存在则生成并持久化
            stored_key = db_manager.get_system_config('jwt_secret_key')
            if stored_key:
                self.jwt_secret_key = stored_key
                logger.debug("JWT密钥已从数据库加载")
            else:
                self.jwt_secret_key = secrets.token_urlsafe(32)
                db_manager.set_system_config(
                    'jwt_secret_key',
                    self.jwt_secret_key,
                    'JWT签名密钥（自动生成）'
                )
                logger.info("JWT密钥已生成并持久化到数据库")

    def generate_admin_password(self, length: int = 12) -> str:
        """生成管理员密码"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def hash_password(self, password: str) -> str:
        """使用 bcrypt 对密码进行哈希"""
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str, password_hash: str) -> bool:
        """验证密码是否与哈希匹配"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False

    def init_admin_password(self) -> Optional[str]:
        """初始化管理员密码，如果不存在则创建。返回新密码或 None"""
        existing_hash = db_manager.get_admin_password_hash()
        if existing_hash:
            logger.info("管理员密码已存在")
            return None

        new_password = self.generate_admin_password()
        password_hash = self.hash_password(new_password)
        success = db_manager.create_admin_password(password_hash, "系统自动生成的管理员密码")

        if success:
            # 不将明文密码写入日志文件，仅返回给调用方
            logger.info("管理员密码已生成（请查看控制台输出）")
            return new_password
        else:
            raise Exception("管理员密码生成失败")

    def verify_password(self, password: str) -> bool:
        """验证管理员密码"""
        stored_hash = db_manager.get_admin_password_hash()
        if not stored_hash:
            return False
        return self.check_password(password, stored_hash)

    def get_admin_session_version(self) -> int:
        """获取管理员会话版本，用于密码变更后让旧JWT失效"""
        try:
            return int(db_manager.get_system_config('admin_session_version', 1))
        except (TypeError, ValueError):
            return 1

    def rotate_admin_session_version(self) -> int:
        """轮换管理员会话版本并持久化"""
        next_version = self.get_admin_session_version() + 1
        db_manager.set_system_config(
            'admin_session_version',
            next_version,
            '管理员JWT会话版本（密码变更后递增）'
        )
        return next_version

    def validate_password_strength(self, password: str) -> list[str]:
        """校验管理员密码强度"""
        issues = []
        if len(password) < 12:
            issues.append("密码长度不能少于12位")

        classes = [
            any(ch.islower() for ch in password),
            any(ch.isupper() for ch in password),
            any(ch.isdigit() for ch in password),
            any(not ch.isalnum() for ch in password),
        ]
        if sum(classes) < 3:
            issues.append("需至少包含大写字母、小写字母、数字、特殊字符中的3类")

        return issues

    def change_admin_password(self, current_password: str, new_password: str) -> Dict[str, Any]:
        """修改管理员密码，并使旧会话立即失效"""
        if not self.verify_password(current_password):
            return {"success": False, "error": "当前密码不正确"}

        if current_password == new_password:
            return {"success": False, "error": "新密码不能与当前密码相同"}

        issues = self.validate_password_strength(new_password)
        if issues:
            return {
                "success": False,
                "error": "新密码不符合安全要求",
                "issues": issues
            }

        password_hash = self.hash_password(new_password)
        success = db_manager.create_admin_password(password_hash, "管理员在后台修改的密码")
        if not success:
            return {"success": False, "error": "管理员密码更新失败"}

        session_version = self.rotate_admin_session_version()
        payload = {
            'user_type': 'admin',
            'session_id': secrets.token_urlsafe(8),
            'session_version': session_version,
            'login_time': datetime.now(timezone.utc).isoformat()
        }
        jwt_token = self.generate_jwt(payload)

        logger.info("管理员密码修改成功，旧会话已失效")
        return {
            "success": True,
            "message": "管理员密码已更新，旧会话已失效",
            "jwt_token": jwt_token
        }

    def generate_jwt(self, payload: Dict[str, Any], expires_hours: int = 24) -> str:
        """生成JWT token"""
        try:
            now = datetime.now(timezone.utc)
            payload['exp'] = now + timedelta(hours=expires_hours)
            payload['iat'] = now
            return jwt.encode(payload, self.jwt_secret_key, algorithm='HS256')
        except Exception as e:
            logger.error(f"JWT生成失败: {e}")
            raise

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT token无效: {e}")
            return None

    def login_with_password(self, admin_password: str) -> Optional[str]:
        """使用管理员密码登录，返回JWT"""
        if self.verify_password(admin_password):
            payload = {
                'user_type': 'admin',
                'session_id': secrets.token_urlsafe(8),
                'session_version': self.get_admin_session_version(),
                'login_time': datetime.now(timezone.utc).isoformat()
            }
            return self.generate_jwt(payload)
        return None


def jwt_required(f):
    """JWT认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Authorization header格式错误'}), 401

        if not token:
            return jsonify({'error': '需要认证token'}), 401

        try:
            auth_manager = current_app.auth_manager
            payload = auth_manager.verify_jwt(token)
            if not payload:
                return jsonify({'error': 'token无效或已过期'}), 401

            if payload.get('user_type') == 'admin':
                current_version = auth_manager.get_admin_session_version()
                token_version = int(payload.get('session_version', 0))
                if token_version != current_version:
                    return jsonify({'error': 'token已失效，请重新登录'}), 401

            request.user = payload
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"JWT验证失败: {e}")
            return jsonify({'error': 'token验证失败'}), 401

    return decorated_function


def create_auth_manager() -> AuthManager:
    """创建认证管理器实例"""
    return AuthManager()
