#!/usr/bin/env python3
"""
SOAR MCP 数据模型
使用SQLAlchemy + Pydantic实现
"""

import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, Boolean, create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field, ConfigDict
from logger_config import logger

Base = declarative_base()


class PlaybookModel(Base):
    """剧本数据库模型"""
    __tablename__ = "playbooks"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))
    playbook_category = Column(String(100), index=True)
    description = Column(Text)  # JSON string
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    remote_update_time = Column(DateTime, index=True)
    playbook_params = Column(Text)  # JSON array
    sync_time = Column(DateTime, default=datetime.now)
    enabled = Column(Boolean, default=True, index=True)
    
    def __repr__(self):
        return f"<Playbook(id={self.id}, name='{self.name}')>"


class AppModel(Base):
    """应用数据库模型"""
    __tablename__ = "apps"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    version = Column(String(100))
    category = Column(String(100), index=True)
    update_time = Column(DateTime)
    remote_update_time = Column(DateTime, index=True)
    require_asset = Column(String(10))
    app_asset_list = Column(Text)  # JSON array
    sync_time = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<App(id={self.id}, name='{self.name}')>"


class ActionModel(Base):
    """动作数据库模型"""
    __tablename__ = "actions"
    
    id = Column(BigInteger, primary_key=True)
    app_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))
    description = Column(Text)
    action_type = Column(String(50))
    classify = Column(String(50))
    logic_language = Column(String(50))
    parameter_variables = Column(Text)  # JSON array
    result_variables = Column(Text)  # JSON array
    update_time = Column(DateTime)
    sync_time = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Action(id={self.id}, name='{self.name}', app_id={self.app_id})>"


class SystemConfigModel(Base):
    """系统配置数据库模型"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(500))
    created_time = Column(DateTime, default=datetime.now)
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SystemConfig(key='{self.key}', value='{self.value}')>"


class AdminPasswordModel(Base):
    """管理员密码数据库模型"""
    __tablename__ = "admin_passwords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    password_hash = Column(String(200), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_time = Column(DateTime, default=datetime.now)
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<AdminPassword(id={self.id}, active={self.is_active})>"


class UserTokenModel(Base):
    """用户Token数据库模型"""
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    permissions = Column(Text)
    created_time = Column(DateTime)
    updated_time = Column(DateTime)
    last_used_time = Column(DateTime)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)

    def __repr__(self):
        return f"<UserToken(id={self.id}, name='{self.name}', active={self.is_active})>"


class AuditLogModel(Base):
    """审计日志数据库模型"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    token_id = Column(Integer, index=True)
    token_name = Column(String(100))
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(200))
    parameters = Column(Text)
    result = Column(String(50))
    error_message = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', result='{self.result}')>"


# ===== Pydantic 模型 =====

class PlaybookParam(BaseModel):
    """剧本参数"""
    cef_column: str = Field(..., description="CEF字段名")
    cef_desc: str = Field(..., description="CEF字段描述")
    value_type: str = Field(..., description="值类型")
    required: bool = Field(default=False, description="是否必填")


class PlaybookData(BaseModel):
    """剧本数据"""
    id: int
    name: str
    display_name: Optional[str] = None
    playbook_category: Optional[str] = None
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    remote_update_time: Optional[datetime] = None
    playbook_params: List[PlaybookParam] = Field(default_factory=list)
    sync_time: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ActionParam(BaseModel):
    """动作参数"""
    name: Optional[str] = Field(default="", description="参数名称")
    required: Optional[bool] = Field(default=False, description="是否必须")
    type: Optional[str] = Field(default="", description="参数类型")
    description: Optional[str] = Field(default="", description="参数描述")
    default_value: Optional[str] = Field(default="", description="默认值")
    order: Optional[int] = Field(default=0, description="顺序")
    
    model_config = ConfigDict(extra="allow")


class ActionResult(BaseModel):
    """动作结果"""
    description: Optional[str] = Field(default="", description="结果描述")
    value_type: Optional[str] = Field(default="", description="值类型")
    data_path: Optional[str] = Field(default="", description="数据路径")
    
    model_config = ConfigDict(extra="allow")


class AppData(BaseModel):
    """应用数据"""
    id: Union[int, str]
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    updateTime: Optional[str] = None
    requireAsset: Optional[Union[str, bool, int]] = None
    appAssetList: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    appActionList: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    createdBy: Optional[Union[int, str]] = None
    modifiedBy: Optional[Union[int, str]] = None
    createdNickName: Optional[str] = None
    modifiedNickName: Optional[str] = None
    createTime: Optional[str] = None
    status: Optional[Union[int, str]] = None
    deleted: Optional[Union[bool, str, int]] = None
    displayName: Optional[str] = None
    readMePath: Optional[str] = None
    iconfilePath: Optional[str] = None
    os: Optional[str] = None
    logicLanguage: Optional[str] = None
    logicLanguageVersion: Optional[str] = None
    assetVariableList: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    logicContent: Optional[str] = None
    actionEngineType: Optional[str] = None
    favState: Optional[Union[int, str]] = None
    usedTimes: Optional[int] = None
    appCategoryList: List[Dict[str, Any]] = Field(default_factory=list)
    appPackageFile: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra="allow")


class ActionData(BaseModel):
    """动作数据"""
    id: int
    app_id: int
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    action_type: Optional[str] = None
    classify: Optional[str] = None
    logic_language: Optional[str] = None
    parameter_variables: List[ActionParam] = Field(default_factory=list)
    result_variables: List[ActionResult] = Field(default_factory=list)
    update_time: Optional[datetime] = None
    sync_time: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class SystemConfigData(BaseModel):
    """系统配置数据"""
    soar_api_url: str = Field(..., description="SOAR服务器API地址")
    soar_api_token: str = Field(..., description="SOAR API Token")
    soar_timeout: int = Field(default=30, description="API超时时间(秒)")
    sync_interval: int = Field(default=14400, description="同步周期(秒)")
    soar_labels: List[str] = Field(default=["MCP"], description="剧本抓取标签列表")
    
    model_config = ConfigDict(from_attributes=True)


# ===== 数据库管理器 =====

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "soar_mcp.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def init_db(self):
        """初始化数据库表"""
        Base.metadata.create_all(bind=self.engine)
        logger.database_info(f"数据库初始化完成: {self.db_path}")
    
    @contextmanager
    def get_session(self):
        """获取数据库会话（上下文管理器，自动关闭）"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    # ===== 辅助方法 =====

    @staticmethod
    def _parse_playbook_params(params_json: str) -> List[PlaybookParam]:
        """解析剧本参数 JSON 字符串"""
        if not params_json:
            return []
        try:
            return [
                PlaybookParam(
                    cef_column=p.get("cefColumn", ""),
                    cef_desc=p.get("cefDesc", ""),
                    value_type=p.get("valueType", ""),
                    required=p.get("required", False)
                ) for p in json.loads(params_json)
            ]
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _playbook_to_data(playbook: PlaybookModel) -> PlaybookData:
        """将 PlaybookModel 转换为 PlaybookData"""
        return PlaybookData(
            id=playbook.id,
            name=playbook.name,
            display_name=playbook.display_name,
            playbook_category=playbook.playbook_category,
            description=playbook.description,
            create_time=playbook.create_time,
            update_time=playbook.update_time,
            remote_update_time=playbook.remote_update_time,
            playbook_params=DatabaseManager._parse_playbook_params(playbook.playbook_params),
            sync_time=playbook.sync_time
        )

    # ===== 剧本操作 =====
    
    def save_playbook(self, playbook_data: PlaybookData, force_update: bool = False) -> Union[bool, str]:
        """保存剧本数据"""
        with self.get_session() as session:
            try:
                params_json = json.dumps([
                    {
                        "cefColumn": param.cef_column,
                        "cefDesc": param.cef_desc,
                        "valueType": param.value_type,
                        "required": param.required
                    } for param in playbook_data.playbook_params
                ], ensure_ascii=False)
                
                existing = session.query(PlaybookModel).filter_by(id=playbook_data.id).first()
                
                if existing:
                    if not force_update and existing.remote_update_time and playbook_data.remote_update_time:
                        if playbook_data.remote_update_time == existing.remote_update_time:
                            return "ignored"
                        elif playbook_data.remote_update_time < existing.remote_update_time:
                            return "ignored"
                    
                    existing.name = playbook_data.name
                    existing.display_name = playbook_data.display_name
                    existing.playbook_category = playbook_data.playbook_category
                    existing.description = playbook_data.description
                    existing.create_time = playbook_data.create_time
                    existing.update_time = playbook_data.update_time
                    existing.remote_update_time = playbook_data.remote_update_time
                    existing.playbook_params = params_json
                    existing.sync_time = datetime.now()
                    logger.sync_success(f"更新剧本 {playbook_data.id}: {playbook_data.name}")
                else:
                    new_playbook = PlaybookModel(
                        id=playbook_data.id,
                        name=playbook_data.name,
                        display_name=playbook_data.display_name,
                        playbook_category=playbook_data.playbook_category,
                        description=playbook_data.description,
                        create_time=playbook_data.create_time,
                        update_time=playbook_data.update_time,
                        remote_update_time=playbook_data.remote_update_time,
                        playbook_params=params_json,
                        sync_time=datetime.now()
                    )
                    session.add(new_playbook)
                    logger.sync_success(f"新增剧本 {playbook_data.id}: {playbook_data.name}")
                
                session.commit()
                return True
                
            except Exception as e:
                session.rollback()
                logger.sync_error(f"保存剧本失败 {playbook_data.id}: {e}")
                return False
    
    def get_playbook(self, playbook_id: int) -> Optional[PlaybookData]:
        """获取单个剧本"""
        with self.get_session() as session:
            try:
                playbook = session.query(PlaybookModel).filter_by(id=playbook_id).first()
                if not playbook:
                    return None
                return self._playbook_to_data(playbook)
            except Exception as e:
                logger.error(f"获取剧本失败 {playbook_id}: {e}")
                return None
    
    def get_playbooks(self, category: Optional[str] = None, limit: int = 100) -> List[PlaybookData]:
        """获取剧本列表（只返回启用的剧本）"""
        with self.get_session() as session:
            try:
                query = session.query(PlaybookModel).filter(PlaybookModel.enabled == True)
                if category:
                    query = query.filter(PlaybookModel.playbook_category == category)
                playbooks = query.limit(limit).all()
                return [self._playbook_to_data(p) for p in playbooks]
            except Exception as e:
                logger.error(f"获取剧本列表失败: {e}")
                return []
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        with self.get_session() as session:
            try:
                total_count = session.query(PlaybookModel).count()
                latest_sync = session.query(PlaybookModel.sync_time).order_by(
                    PlaybookModel.sync_time.desc()
                ).first()
                return {
                    "total_playbooks": total_count,
                    "latest_sync_time": latest_sync[0] if latest_sync else None
                }
            except Exception as e:
                logger.error(f"获取同步统计失败: {e}")
                return {"total_playbooks": 0, "latest_sync_time": None}
    
    def save_app(self, app_data: AppData, force_update: bool = False) -> Union[bool, str]:
        """保存应用数据"""
        with self.get_session() as session:
            try:
                asset_list_json = json.dumps(app_data.appAssetList, ensure_ascii=False)
                
                update_time = None
                remote_update_time = None
                if app_data.updateTime:
                    try:
                        if isinstance(app_data.updateTime, str) and "T" in app_data.updateTime:
                            update_time = datetime.fromisoformat(app_data.updateTime.replace("Z", "+00:00"))
                            remote_update_time = update_time
                        elif isinstance(app_data.updateTime, (int, float, str)):
                            timestamp = int(app_data.updateTime) / 1000
                            update_time = datetime.fromtimestamp(timestamp)
                            remote_update_time = update_time
                    except (ValueError, TypeError):
                        pass
                
                existing = session.query(AppModel).filter_by(id=app_data.id).first()
                
                if existing:
                    if not force_update:
                        if remote_update_time is None:
                            return "ignored"
                        if existing.remote_update_time and remote_update_time == existing.remote_update_time:
                            return "ignored"
                        elif existing.remote_update_time and remote_update_time < existing.remote_update_time:
                            return "ignored"
                    
                    existing.name = app_data.name
                    existing.description = app_data.description
                    existing.version = app_data.version
                    existing.category = app_data.category
                    existing.update_time = update_time
                    existing.remote_update_time = remote_update_time
                    existing.require_asset = app_data.requireAsset
                    existing.app_asset_list = asset_list_json
                    existing.sync_time = datetime.now()
                    logger.sync_success(f"更新应用 {app_data.id}: {app_data.name}")
                else:
                    new_app = AppModel(
                        id=app_data.id,
                        name=app_data.name,
                        description=app_data.description,
                        version=app_data.version,
                        category=app_data.category,
                        update_time=update_time,
                        remote_update_time=remote_update_time,
                        require_asset=app_data.requireAsset,
                        app_asset_list=asset_list_json,
                        sync_time=datetime.now()
                    )
                    session.add(new_app)
                    logger.sync_success(f"新增应用 {app_data.id}: {app_data.name}")
                
                session.commit()
                return True
                
            except Exception as e:
                session.rollback()
                logger.sync_error(f"保存应用失败 {app_data.id}: {e}")
                return False
    
    def delete_actions_by_app_id(self, app_id: int) -> int:
        """删除指定应用的所有动作"""
        with self.get_session() as session:
            try:
                deleted_count = session.query(ActionModel).filter_by(app_id=app_id).delete()
                session.commit()
                return deleted_count
            except Exception as e:
                session.rollback()
                logger.sync_error(f"删除应用动作失败 {app_id}: {e}")
                return 0
    
    def batch_save_actions(self, actions_data: List[ActionData]) -> int:
        """批量保存动作数据"""
        with self.get_session() as session:
            try:
                success_count = 0
                for action_data in actions_data:
                    parameter_vars_json = json.dumps([
                        {
                            "name": param.name,
                            "required": param.required,
                            "type": param.type,
                            "description": param.description,
                            "defaultValue": param.default_value,
                            "order": param.order
                        } for param in action_data.parameter_variables
                    ], ensure_ascii=False)
                    
                    result_vars_json = json.dumps([
                        {
                            "description": result.description,
                            "valueType": result.value_type,
                            "dataPath": result.data_path
                        } for result in action_data.result_variables
                    ], ensure_ascii=False)
                    
                    new_action = ActionModel(
                        id=action_data.id,
                        app_id=action_data.app_id,
                        name=action_data.name,
                        display_name=action_data.display_name,
                        description=action_data.description,
                        action_type=action_data.action_type,
                        classify=action_data.classify,
                        logic_language=action_data.logic_language,
                        parameter_variables=parameter_vars_json,
                        result_variables=result_vars_json,
                        update_time=action_data.update_time,
                        sync_time=datetime.now()
                    )
                    session.add(new_action)
                    success_count += 1
                
                session.commit()
                return success_count
                
            except Exception as e:
                session.rollback()
                logger.sync_error(f"批量保存动作失败: {e}")
                return 0
    
    def get_apps_stats(self) -> Dict[str, Any]:
        """获取应用统计信息"""
        with self.get_session() as session:
            try:
                total_apps = session.query(AppModel).count()
                total_actions = session.query(ActionModel).count()
                return {"total_apps": total_apps, "total_actions": total_actions}
            except Exception as e:
                logger.error(f"获取应用统计失败: {e}")
                return {"total_apps": 0, "total_actions": 0}
    
    def get_playbooks_stats(self) -> Dict[str, Any]:
        """获取剧本统计信息"""
        with self.get_session() as session:
            try:
                total_playbooks = session.query(PlaybookModel).count()
                enabled_playbooks = session.query(PlaybookModel).filter_by(enabled=True).count()
                return {
                    "total_playbooks": total_playbooks,
                    "enabled_playbooks": enabled_playbooks,
                    "disabled_playbooks": total_playbooks - enabled_playbooks
                }
            except Exception as e:
                logger.error(f"获取剧本统计失败: {e}")
                return {"total_playbooks": 0, "enabled_playbooks": 0, "disabled_playbooks": 0}
    
    def get_last_sync_time(self) -> Optional[str]:
        """获取最后同步时间"""
        try:
            last_sync_config = self.get_system_config("last_sync_time")
            if last_sync_config:
                if isinstance(last_sync_config, str):
                    try:
                        last_sync_dt = datetime.fromisoformat(last_sync_config.replace("Z", "+00:00"))
                        return last_sync_dt.strftime("%Y/%m/%d %H:%M:%S")
                    except ValueError:
                        pass
                elif isinstance(last_sync_config, datetime):
                    return last_sync_config.strftime("%Y/%m/%d %H:%M:%S")

            with self.get_session() as session:
                playbook_sync = session.query(PlaybookModel.sync_time).order_by(
                    PlaybookModel.sync_time.desc()
                ).first()
                app_sync = session.query(AppModel.sync_time).order_by(
                    AppModel.sync_time.desc()
                ).first()

                playbook_time = playbook_sync[0] if playbook_sync else None
                app_time = app_sync[0] if app_sync else None

                latest_time = None
                if playbook_time and app_time:
                    latest_time = max(playbook_time, app_time)
                elif playbook_time:
                    latest_time = playbook_time
                elif app_time:
                    latest_time = app_time

                return latest_time.strftime("%Y/%m/%d %H:%M:%S") if latest_time else None

        except Exception as e:
            logger.error(f"获取最后同步时间失败: {e}")
            return None

    def update_last_sync_time(self) -> bool:
        """更新最后同步时间"""
        try:
            return self.set_system_config(
                "last_sync_time",
                datetime.now().isoformat(),
                "最后一次数据同步的时间"
            )
        except Exception as e:
            logger.error(f"更新最后同步时间失败: {e}")
            return False

    def get_playbooks_admin(self, category: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """获取所有剧本列表（管理界面，含启用状态）"""
        with self.get_session() as session:
            try:
                query = session.query(PlaybookModel)
                if category:
                    query = query.filter(PlaybookModel.playbook_category == category)
                playbooks = query.order_by(PlaybookModel.id).limit(limit).all()
                
                return [{
                    "id": str(p.id),
                    "name": p.name,
                    "displayName": p.display_name or p.name,
                    "playbookCategory": p.playbook_category or "未分类",
                    "description": p.description or "",
                    "enabled": p.enabled if p.enabled is not None else True,
                    "createTime": p.create_time.isoformat() if p.create_time else None,
                    "updateTime": p.update_time.isoformat() if p.update_time else None,
                    "syncTime": p.sync_time.isoformat() if p.sync_time else None
                } for p in playbooks]
                
            except Exception as e:
                logger.error(f"获取剧本管理列表失败: {e}")
                return []
    
    def get_playbook_by_id(self, playbook_id: int) -> Optional[Dict]:
        """根据ID获取单个剧本详情"""
        with self.get_session() as session:
            try:
                playbook = session.query(PlaybookModel).filter_by(id=playbook_id).first()
                if not playbook:
                    return None
                return {
                    "id": str(playbook.id),
                    "name": playbook.name,
                    "displayName": playbook.display_name or playbook.name,
                    "playbookCategory": playbook.playbook_category or "未分类",
                    "description": playbook.description or "",
                    "enabled": playbook.enabled if playbook.enabled is not None else True,
                    "playbookParams": playbook.playbook_params or "[]",
                    "createTime": playbook.create_time.isoformat() if playbook.create_time else None,
                    "updateTime": playbook.update_time.isoformat() if playbook.update_time else None,
                    "syncTime": playbook.sync_time.isoformat() if playbook.sync_time else None,
                    "remoteUpdateTime": playbook.remote_update_time.isoformat() if playbook.remote_update_time else None
                }
            except Exception as e:
                logger.error(f"获取剧本详情失败 {playbook_id}: {e}")
                return None

    def update_playbook_status(self, playbook_id: int, enabled: bool) -> bool:
        """更新剧本启用状态"""
        with self.get_session() as session:
            try:
                playbook = session.query(PlaybookModel).filter_by(id=playbook_id).first()
                if not playbook:
                    return False
                playbook.enabled = enabled
                playbook.update_time = datetime.now()
                session.commit()
                logger.info(f"剧本 {playbook_id} 状态已更新为: {'启用' if enabled else '禁用'}")
                return True
            except Exception as e:
                logger.error(f"更新剧本状态失败: {e}")
                session.rollback()
                return False

    # ===== 系统配置操作 =====

    def get_system_config(self, key: str, default_value: Any = None) -> Any:
        """获取系统配置值"""
        with self.get_session() as session:
            try:
                config = session.query(SystemConfigModel).filter_by(key=key).first()
                if config:
                    try:
                        return json.loads(config.value)
                    except json.JSONDecodeError:
                        return config.value
                return default_value
            except Exception as e:
                logger.error(f"获取系统配置失败 {key}: {e}")
                return default_value
    
    def set_system_config(self, key: str, value: Any, description: str = None) -> bool:
        """设置系统配置值"""
        with self.get_session() as session:
            try:
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, ensure_ascii=False)
                else:
                    value_str = str(value)
                
                config = session.query(SystemConfigModel).filter_by(key=key).first()
                if config:
                    config.value = value_str
                    config.updated_time = datetime.now()
                    if description:
                        config.description = description
                else:
                    config = SystemConfigModel(key=key, value=value_str, description=description or "")
                    session.add(config)
                
                session.commit()
                # 敏感信息脱敏
                if key in ['soar_api_token', 'jwt_secret_key', 'admin_password']:
                    display_value = str(value)
                    if len(display_value) > 10:
                        display_value = display_value[:6] + '****' + display_value[-4:]
                    else:
                        display_value = '****'
                    logger.info(f"系统配置已更新: {key} = {display_value}")
                else:
                    logger.info(f"系统配置已更新: {key} = {value}")
                return True
            except Exception as e:
                logger.error(f"设置系统配置失败 {key}: {e}")
                session.rollback()
                return False
    
    def get_all_system_configs(self) -> Dict[str, Any]:
        """获取所有系统配置"""
        with self.get_session() as session:
            try:
                configs = session.query(SystemConfigModel).all()
                result = {}
                for config in configs:
                    try:
                        result[config.key] = json.loads(config.value)
                    except json.JSONDecodeError:
                        result[config.key] = config.value
                return result
            except Exception as e:
                logger.error(f"获取所有系统配置失败: {e}")
                return {}

    # ===== 认证操作 =====

    def create_admin_password(self, password_hash: str, description: str = None) -> bool:
        """创建管理员密码"""
        with self.get_session() as session:
            try:
                session.query(AdminPasswordModel).delete()
                new_password = AdminPasswordModel(
                    password_hash=password_hash, description=description, is_active=True
                )
                session.add(new_password)
                session.commit()
                logger.info("创建管理员密码成功")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"创建管理员密码失败: {e}")
                return False

    def get_admin_password_hash(self) -> Optional[str]:
        """获取有效的管理员密码哈希"""
        with self.get_session() as session:
            try:
                obj = session.query(AdminPasswordModel).filter(AdminPasswordModel.is_active == True).first()
                return obj.password_hash if obj else None
            except Exception as e:
                logger.error(f"获取管理员密码失败: {e}")
                return None

    def verify_admin_password(self, password_hash: str) -> bool:
        """验证管理员密码哈希是否有效（旧接口，bcrypt 版本不再使用）"""
        with self.get_session() as session:
            try:
                obj = session.query(AdminPasswordModel).filter(
                    AdminPasswordModel.password_hash == password_hash,
                    AdminPasswordModel.is_active == True
                ).first()
                return obj is not None
            except Exception as e:
                logger.error(f"验证管理员密码失败: {e}")
                return False

    def init_default_configs(self):
        """初始化默认系统配置"""
        try:
            existing_configs = self.get_all_system_configs()
            if not existing_configs:
                logger.info("初始化默认系统配置...")
                import os
                from dotenv import load_dotenv
                env_path = ".env"
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    logger.info("从.env文件迁移配置到数据库")

                default_configs = {
                    "soar_api_url": os.getenv("API_URL", ""),
                    "soar_api_token": os.getenv("API_TOKEN", ""),
                    "soar_timeout": int(os.getenv("SOAR_TIMEOUT", "30")),
                    "sync_interval": int(os.getenv("SYNC_INTERVAL", "14400")),
                    "soar_labels": ["MCP"],
                    "ssl_verify": os.getenv("SSL_VERIFY", "1") != "0"
                }
                for key, value in default_configs.items():
                    self.set_system_config(key, value, f"系统默认配置: {key}")
                logger.info("默认系统配置初始化完成")
            else:
                logger.info("系统配置已存在，跳过初始化")
        except Exception as e:
            logger.error(f"初始化默认系统配置失败: {e}")

    # ===== Token 操作 =====

    def create_user_token(self, name: str, expires_in_days: int = None) -> Optional[str]:
        """创建用户Token"""
        with self.get_session() as session:
            try:
                import secrets
                from datetime import timedelta
                token = secrets.token_urlsafe(32)
                expires_at = None
                if expires_in_days:
                    expires_at = datetime.now() + timedelta(days=expires_in_days)
                new_token = UserTokenModel(token=token, name=name, expires_at=expires_at, is_active=True)
                session.add(new_token)
                session.commit()
                logger.info(f"创建用户Token成功: {name}")
                return token
            except Exception as e:
                session.rollback()
                logger.error(f"创建用户Token失败: {e}")
                return None

    def get_user_tokens(self) -> List[Dict]:
        """获取所有用户Token列表"""
        with self.get_session() as session:
            try:
                tokens = session.query(UserTokenModel).order_by(UserTokenModel.created_at.desc()).all()
                return [{
                    "id": t.id,
                    "token": t.token,
                    "name": t.name,
                    "description": t.description,
                    "is_active": t.is_active,
                    "permissions": t.permissions,
                    "usage_count": t.usage_count or 0,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None
                } for t in tokens]
            except Exception as e:
                logger.error(f"获取用户Token列表失败: {e}")
                return []

    def verify_token(self, token: str) -> bool:
        """验证Token是否有效"""
        with self.get_session() as session:
            try:
                token_obj = session.query(UserTokenModel).filter(
                    UserTokenModel.token == token,
                    UserTokenModel.is_active == True
                ).first()

                if not token_obj:
                    return False
                if token_obj.expires_at and datetime.now() > token_obj.expires_at:
                    return False

                token_obj.last_used_at = datetime.now()
                if token_obj.usage_count is None:
                    token_obj.usage_count = 1
                else:
                    token_obj.usage_count += 1
                session.commit()
                return True
            except Exception as e:
                logger.error(f"验证Token失败: {e}")
                return False

    def delete_user_token(self, token_id: int) -> bool:
        """删除用户Token"""
        with self.get_session() as session:
            try:
                token = session.query(UserTokenModel).filter_by(id=token_id).first()
                if not token:
                    return False
                session.delete(token)
                session.commit()
                logger.info(f"删除用户Token成功: {token.name}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"删除用户Token失败: {e}")
                return False

    def update_token_status(self, token_id: int, is_active: bool) -> bool:
        """更新Token启用状态"""
        with self.get_session() as session:
            try:
                token = session.query(UserTokenModel).filter_by(id=token_id).first()
                if not token:
                    return False
                token.is_active = is_active
                session.commit()
                logger.info(f"Token状态更新: {token.name} -> {'启用' if is_active else '禁用'}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"更新Token状态失败: {e}")
                return False

    # ===== 审计日志 =====

    def log_audit_event(self, action: str, resource: str = None, parameters: dict = None,
                       result: str = "success", error_message: str = None,
                       token_info: dict = None, ip_address: str = None, user_agent: str = None) -> bool:
        """记录审计日志"""
        with self.get_session() as session:
            try:
                params_json = json.dumps(parameters, ensure_ascii=False) if parameters else None
                audit_log = AuditLogModel(
                    action=action,
                    resource=resource,
                    parameters=params_json,
                    result=result,
                    error_message=error_message,
                    token_id=token_info.get('id') if token_info else None,
                    token_name=token_info.get('name') if token_info else None,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                session.add(audit_log)
                session.commit()
                logger.debug(f"审计日志: {action} -> {result}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"记录审计日志失败: {e}")
                return False

    def get_audit_logs(self, limit: int = 100, token_id: int = None, action: str = None) -> List[Dict]:
        """获取审计日志列表"""
        with self.get_session() as session:
            try:
                query = session.query(AuditLogModel)
                if token_id:
                    query = query.filter(AuditLogModel.token_id == token_id)
                if action:
                    query = query.filter(AuditLogModel.action == action)
                logs = query.order_by(AuditLogModel.timestamp.desc()).limit(limit).all()

                result = []
                for log in logs:
                    params = None
                    if log.parameters:
                        try:
                            params = json.loads(log.parameters)
                        except json.JSONDecodeError:
                            params = log.parameters
                    result.append({
                        "id": log.id,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "token_id": log.token_id,
                        "token_name": log.token_name,
                        "action": log.action,
                        "resource": log.resource,
                        "parameters": params,
                        "result": log.result,
                        "error_message": log.error_message,
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent
                    })
                return result
            except Exception as e:
                logger.error(f"获取审计日志失败: {e}")
                return []

    def get_token_by_value(self, token: str) -> Optional[Dict]:
        """根据Token值获取Token信息"""
        with self.get_session() as session:
            try:
                token_obj = session.query(UserTokenModel).filter(
                    UserTokenModel.token == token,
                    UserTokenModel.is_active == True
                ).first()
                if not token_obj:
                    return None
                if token_obj.expires_at and datetime.now() > token_obj.expires_at:
                    return None
                return {
                    "id": token_obj.id,
                    "name": token_obj.name,
                    "token": token_obj.token,
                    "is_active": token_obj.is_active,
                    "usage_count": token_obj.usage_count or 0,
                    "created_at": token_obj.created_at.isoformat() if token_obj.created_at else None,
                    "expires_at": token_obj.expires_at.isoformat() if token_obj.expires_at else None,
                    "last_used_at": token_obj.last_used_at.isoformat() if token_obj.last_used_at else None
                }
            except Exception as e:
                logger.error(f"获取Token信息失败: {e}")
                return None


# 全局数据库管理器实例
db_manager = DatabaseManager()
