#!/usr/bin/env python3
"""
手动测试新增的MCP工具功能
通过直接调用工具逻辑验证功能
"""

import json
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import DatabaseManager, db_manager

# Mock executions storage
MOCK_EXECUTIONS = {}

def list_playbooks_quick_logic(category: Optional[str] = None, limit: int = 100) -> str:
    """实现list_playbooks_quick的逻辑"""
    try:
        playbooks = db_manager.get_playbooks(category=category, limit=limit)
        
        result = {
            "total": len(playbooks),
            "playbooks": [
                {
                    "id": p.id,
                    "name": p.name,
                    "displayName": p.display_name
                } for p in playbooks
            ]
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"获取剧本列表失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def list_playbooks_detailed_logic(category: Optional[str] = None, limit: int = 50) -> str:
    """实现list_playbooks_detailed的逻辑"""
    try:
        playbooks = db_manager.get_playbooks(category=category, limit=limit)
        
        result = {
            "total": len(playbooks),
            "playbooks": [
                {
                    "id": p.id,
                    "name": p.name,
                    "displayName": p.display_name,
                    "playbookCategory": p.playbook_category,
                    "description": p.description,
                    "createTime": p.create_time.isoformat() if p.create_time else None,
                    "updateTime": p.update_time.isoformat() if p.update_time else None,
                    "playbookParams": [
                        {
                            "cefColumn": param.cef_column,
                            "cefDesc": param.cef_desc,
                            "valueType": param.value_type
                        } for param in p.playbook_params
                    ]
                } for p in playbooks
            ]
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"获取详细剧本列表失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def query_playbook_execution_params_logic(playbook_id: int) -> str:
    """实现query_playbook_execution_params的逻辑"""
    try:
        playbook = db_manager.get_playbook(playbook_id)
        
        if not playbook:
            return json.dumps({
                "error": f"未找到剧本 ID: {playbook_id}"
            }, ensure_ascii=False, indent=2)
        
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
        return json.dumps({
            "error": f"查询剧本参数失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def execute_playbook_advanced_logic(event_id: str, playbook_id: int, parameters: Optional[dict] = None) -> str:
    """实现execute_playbook_advanced的逻辑"""
    if parameters is None:
        parameters = {}
    
    try:
        playbook = db_manager.get_playbook(playbook_id)
        if not playbook:
            return json.dumps({
                "error": f"未找到剧本 ID: {playbook_id}"
            }, ensure_ascii=False, indent=2)
        
        # 生成唯一的活动ID
        activity_id = f"activity_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{playbook_id}"
        
        execution_data = {
            "activityId": activity_id,
            "status": "RUNNING",
            "eventId": event_id,
            "playbookId": playbook_id,
            "playbookName": playbook.name,
            "playbookDisplayName": playbook.display_name,
            "parameters": parameters,
            "startTime": datetime.now().isoformat(),
            "message": "剧本执行已启动"
        }
        
        # 存储执行状态用于后续查询
        MOCK_EXECUTIONS[activity_id] = {
            **execution_data,
            "endTime": None,
            "result": None,
            "logs": []
        }
        
        return json.dumps(execution_data, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"执行剧本失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def query_playbook_execution_status_by_activity_id_logic(activity_id: str) -> str:
    """实现query_status_by_activity_id的逻辑"""
    try:
        if activity_id not in MOCK_EXECUTIONS:
            return json.dumps({
                "error": f"未找到执行活动: {activity_id}"
            }, ensure_ascii=False, indent=2)
        
        execution = MOCK_EXECUTIONS[activity_id]
        
        current_time = datetime.now()
        start_time = datetime.fromisoformat(execution["startTime"])
        elapsed_seconds = (current_time - start_time).total_seconds()
        
        # 模拟执行状态变化
        if elapsed_seconds > 30:  # 30秒后完成
            execution["status"] = "COMPLETED"
            execution["endTime"] = current_time.isoformat()
            execution["message"] = "剧本执行完成"
        elif elapsed_seconds > 10:  # 10秒后进入执行中
            execution["status"] = "EXECUTING"
            execution["message"] = "剧本正在执行中"
        else:
            execution["status"] = "STARTING"
            execution["message"] = "剧本正在启动"
        
        result = {
            "activityId": activity_id,
            "status": execution["status"],
            "message": execution["message"],
            "startTime": execution["startTime"],
            "endTime": execution.get("endTime"),
            "elapsedSeconds": int(elapsed_seconds)
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"查询执行状态失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

def query_playbook_execution_overview_by_activity_id_logic(activity_id: str) -> str:
    """实现query_playbook_execution_overview_by_activity_id的逻辑"""
    try:
        if activity_id not in MOCK_EXECUTIONS:
            return json.dumps({
                "error": f"未找到执行活动: {activity_id}"
            }, ensure_ascii=False, indent=2)
        
        execution = MOCK_EXECUTIONS[activity_id]
        
        current_time = datetime.now()
        start_time = datetime.fromisoformat(execution["startTime"])
        elapsed_seconds = (current_time - start_time).total_seconds()
        
        if elapsed_seconds > 30:  # 完成状态
            execution["status"] = "COMPLETED"
            execution["endTime"] = current_time.isoformat()
            
            # 生成模拟结果
            if "result" not in execution or execution["result"] is None:
                execution["result"] = {
                    "success": True,
                    "executedSteps": 5,
                    "totalSteps": 5,
                    "outputs": {
                        "processedEvents": 1,
                        "actionsExecuted": 3,
                        "notifications": 2
                    }
                }
                execution["logs"] = [
                    {"timestamp": execution["startTime"], "level": "INFO", "message": "剧本执行开始"},
                    {"timestamp": (start_time + timedelta(seconds=5)).isoformat(), "level": "INFO", "message": "步骤1: 事件分析完成"},
                    {"timestamp": (start_time + timedelta(seconds=15)).isoformat(), "level": "INFO", "message": "步骤2: 威胁检测完成"},
                    {"timestamp": (start_time + timedelta(seconds=25)).isoformat(), "level": "INFO", "message": "步骤3: 响应动作执行完成"},
                    {"timestamp": execution["endTime"], "level": "INFO", "message": "剧本执行成功完成"}
                ]
        
        result = {
            "activityId": activity_id,
            "status": execution["status"],
            "eventId": execution["eventId"],
            "playbookId": execution["playbookId"],
            "playbookName": execution["playbookName"],
            "startTime": execution["startTime"],
            "endTime": execution.get("endTime"),
            "parameters": execution["parameters"],
            "result": execution.get("result"),
            "logs": execution.get("logs", []),
            "message": execution.get("message", "获取结果成功")
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"查询执行结果失败: {str(e)}"
        }, ensure_ascii=False, indent=2)

async def test_all_tools():
    """测试所有新增工具"""
    print("🧪 测试新增的MCP工具功能 (手动版本)")
    print("=" * 60)
    
    try:
        # 1. 测试 list_playbooks_quick
        print("\n1️⃣ 测试 list_playbooks_quick - 获取简洁剧本列表")
        result = list_playbooks_quick_logic(limit=5)
        data = json.loads(result)
        if "error" not in data:
            print(f"   📊 总计: {data.get('total', 0)} 个剧本")
            print(f"   📋 前3个剧本:")
            for pb in data.get('playbooks', [])[:3]:
                print(f"      - ID: {pb['id']}, 名称: {pb['name']}, 显示名: {pb['displayName']}")
        else:
            print(f"   ❌ 错误: {data['error']}")
        
        # 2. 测试 list_playbooks_detailed
        print("\n2️⃣ 测试 list_playbooks_detailed - 获取详细剧本列表")
        result = list_playbooks_detailed_logic(limit=2)
        data = json.loads(result)
        if "error" not in data:
            print(f"   📊 总计: {data.get('total', 0)} 个剧本")
            for pb in data.get('playbooks', [])[:1]:
                print(f"   📋 剧本详情:")
                print(f"      - ID: {pb['id']}")
                print(f"      - 名称: {pb['name']}")
                print(f"      - 显示名: {pb['displayName']}")
                print(f"      - 分类: {pb['playbookCategory']}")
                print(f"      - 参数数量: {len(pb.get('playbookParams', []))}")
                if pb.get('playbookParams'):
                    print(f"      - 参数详情:")
                    for param in pb['playbookParams'][:2]:
                        print(f"        • {param['cefColumn']}: {param['cefDesc']} ({param['valueType']})")
        else:
            print(f"   ❌ 错误: {data['error']}")
        
        # 获取一个剧本ID用于后续测试
        playbook_id = None
        if "error" not in data:
            playbooks = data.get('playbooks', [])
            if playbooks:
                playbook_id = playbooks[0]['id']
        
        if not playbook_id:
            print("   ⚠️  未找到可用的剧本ID，跳过后续测试")
            return
        
        # 3. 测试 query_playbook_execution_params
        print(f"\n3️⃣ 测试 query_playbook_execution_params - 查询剧本执行参数 (ID: {playbook_id})")
        result = query_playbook_execution_params_logic(playbook_id)
        data = json.loads(result)
        if "error" not in data:
            print(f"   📋 剧本: {data.get('playbookDisplayName', 'N/A')}")
            required_params = data.get('requiredParams', [])
            print(f"   📊 必需参数: {len(required_params)} 个")
            for param in required_params[:3]:
                print(f"      - {param['paramName']}: {param['paramDesc']} ({param['paramType']})")
        else:
            print(f"   ❌ 错误: {data['error']}")
        
        # 4. 测试 execute_playbook_advanced
        print(f"\n4️⃣ 测试 execute_playbook_advanced - 执行剧本 (ID: {playbook_id})")
        mock_event_id = "event_test_001"
        mock_params = {
            "sourceAddress": "192.168.1.100",
            "destinationPort": "443"
        }
        
        result = execute_playbook_advanced_logic(mock_event_id, playbook_id, mock_params)
        data = json.loads(result)
        
        activity_id = None
        if "error" not in data:
            activity_id = data.get('activityId')
            print(f"   🚀 执行启动成功!")
            print(f"   📄 活动ID: {activity_id}")
            print(f"   📊 状态: {data.get('status')}")
            print(f"   💬 消息: {data.get('message')}")
            print(f"   🕐 开始时间: {data.get('startTime')}")
        else:
            print(f"   ❌ 错误: {data['error']}")
        
        if not activity_id:
            print("   ⚠️  未获取到活动ID，跳过状态和结果查询测试")
            return
        
        # 5. 测试 query_status_by_activity_id - 多次查询状态变化
        print(f"\n5️⃣ 测试 query_status_by_activity_id - 查询执行状态 (活动ID: {activity_id})")

        for i in range(3):
            print(f"   🔍 查询 #{i+1}:")
            result = query_playbook_execution_status_by_activity_id_logic(activity_id)
            data = json.loads(result)
            if "error" not in data:
                print(f"      - 状态: {data.get('status')}")
                print(f"      - 消息: {data.get('message')}")
                print(f"      - 运行时间: {data.get('elapsedSeconds')} 秒")
            else:
                print(f"      ❌ 错误: {data['error']}")
            
            if i < 2:  # 不是最后一次查询
                print("      ⏳ 等待15秒...")
                await asyncio.sleep(15)
        
        # 6. 测试 query_playbook_execution_overview_by_activity_id
        print(f"\n6️⃣ 测试 query_playbook_execution_overview_by_activity_id - 查询执行概览结果 (活动ID: {activity_id})")

        # 等待执行完成
        print("   ⏳ 等待剧本执行完成...")
        await asyncio.sleep(35)  # 等待超过30秒确保执行完成

        result = query_playbook_execution_overview_by_activity_id_logic(activity_id)
        data = json.loads(result)
        if "error" not in data:
            print(f"   📊 最终状态: {data.get('status')}")
            print(f"   🎯 剧本: {data.get('playbookName')}")
            print(f"   📄 事件ID: {data.get('eventId')}")
            print(f"   🕐 开始时间: {data.get('startTime')}")
            print(f"   🏁 结束时间: {data.get('endTime')}")
            
            result_data = data.get('result', {})
            if result_data:
                print(f"   ✅ 执行结果:")
                print(f"      - 成功: {result_data.get('success')}")
                print(f"      - 已执行步骤: {result_data.get('executedSteps')}/{result_data.get('totalSteps')}")
                outputs = result_data.get('outputs', {})
                if outputs:
                    print(f"      - 处理事件: {outputs.get('processedEvents')}")
                    print(f"      - 执行动作: {outputs.get('actionsExecuted')}")
                    print(f"      - 发送通知: {outputs.get('notifications')}")
            
            logs = data.get('logs', [])
            if logs:
                print(f"   📝 执行日志 ({len(logs)} 条):")
                for log in logs[-3:]:  # 显示最后3条日志
                    print(f"      - [{log.get('level')}] {log.get('message')}")
        else:
            print(f"   ❌ 错误: {data['error']}")
        
        print("\n" + "=" * 60)
        print("✅ 所有新增MCP工具测试完成!")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all_tools())
