#!/usr/bin/env python3
"""
测试新增的MCP工具
验证6个剧本管理和执行工具的功能
"""

import asyncio
import json
import time
import aiohttp

class SimpleMCPClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    async def call_tool(self, tool_name, parameters=None):
        """调用MCP工具"""
        if parameters is None:
            parameters = {}
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", {}).get("content", [{}])[0].get("text", "")
                    else:
                        text = await response.text()
                        print(f"HTTP Error {response.status}: {text}")
                        return None
        except Exception as e:
            print(f"请求异常: {e}")
            return None

async def test_new_mcp_tools():
    """测试新增的MCP工具"""
    
    print("🧪 测试新增的MCP工具功能")
    print("=" * 60)
    
    client = SimpleMCPClient("http://127.0.0.1:12345/mcp")
    
    try:
        # 1. 测试 list_playbooks_quick
        print("\n1️⃣ 测试 list_playbooks_quick - 获取简洁剧本列表")
        result = await client.call_tool("list_playbooks_quick", {"limit": 5})
        if result:
            data = json.loads(result)
            print(f"   📊 总计: {data.get('total', 0)} 个剧本")
            print(f"   📋 前5个剧本:")
            for pb in data.get('playbooks', [])[:3]:
                print(f"      - ID: {pb['id']}, 名称: {pb['name']}, 显示名: {pb['displayName']}")
        else:
            print("   ❌ 工具调用失败")
        
        # 2. 测试 list_playbooks_detailed  
        print("\n2️⃣ 测试 list_playbooks_detailed - 获取详细剧本列表")
        result = await client.call_tool("list_playbooks_detailed", {"limit": 2})
        if result:
            data = json.loads(result)
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
            print("   ❌ 工具调用失败")
        
        # 获取一个剧本ID用于后续测试
        playbook_id = None
        if result:
            data = json.loads(result)
            playbooks = data.get('playbooks', [])
            if playbooks:
                playbook_id = playbooks[0]['id']
        
        if not playbook_id:
            print("   ⚠️  未找到可用的剧本ID，跳过后续测试")
            return
        
        # 3. 测试 query_playbook_execution_params
        print(f"\n3️⃣ 测试 query_playbook_execution_params - 查询剧本执行参数 (ID: {playbook_id})")
        result = await client.call_tool("query_playbook_execution_params", {"playbook_id": playbook_id})
        if result:
            data = json.loads(result)
            print(f"   📋 剧本: {data.get('playbookDisplayName', 'N/A')}")
            required_params = data.get('requiredParams', [])
            print(f"   📊 必需参数: {len(required_params)} 个")
            for param in required_params[:3]:
                print(f"      - {param['paramName']}: {param['paramDesc']} ({param['paramType']})")
        else:
            print("   ❌ 工具调用失败")
        
        # 4. 测试 execute_playbook_advanced
        print(f"\n4️⃣ 测试 execute_playbook_advanced - 执行剧本 (ID: {playbook_id})")
        mock_event_id = "event_test_001"
        mock_params = {
            "sourceAddress": "192.168.1.100",
            "destinationPort": "443"
        }
        
        result = await client.call_tool("execute_playbook_advanced", {
            "event_id": mock_event_id,
            "playbook_id": playbook_id,
            "parameters": mock_params
        })
        
        activity_id = None
        if result:
            data = json.loads(result)
            activity_id = data.get('activityId')
            print(f"   🚀 执行启动成功!")
            print(f"   📄 活动ID: {activity_id}")
            print(f"   📊 状态: {data.get('status')}")
            print(f"   💬 消息: {data.get('message')}")
            print(f"   🕐 开始时间: {data.get('startTime')}")
        else:
            print("   ❌ 工具调用失败")
        
        if not activity_id:
            print("   ⚠️  未获取到活动ID，跳过状态和结果查询测试")
            return
        
        # 5. 测试 query_playbook_execution_status_by_activity_id - 多次查询状态变化
        print(f"\n5️⃣ 测试 query_playbook_execution_status_by_activity_id - 查询执行状态 (活动ID: {activity_id})")

        for i in range(3):
            print(f"   🔍 查询 #{i+1}:")
            result = await client.call_tool("query_playbook_execution_status_by_activity_id", {"activity_id": activity_id})
            if result:
                data = json.loads(result)
                print(f"      - 状态: {data.get('status')}")
                print(f"      - 消息: {data.get('message')}")
                print(f"      - 运行时间: {data.get('elapsedSeconds')} 秒")
            else:
                print("      ❌ 查询失败")
            
            if i < 2:  # 不是最后一次查询
                print("      ⏳ 等待15秒...")
                await asyncio.sleep(15)
        
        # 6. 测试 query_playbook_execution_overview_by_activity_id
        print(f"\n6️⃣ 测试 query_playbook_execution_overview_by_activity_id - 查询概览结果 (活动ID: {activity_id})")

        # 等待执行完成
        print("   ⏳ 等待剧本执行完成...")
        await asyncio.sleep(35)  # 等待超过30秒确保执行完成

        result = await client.call_tool("query_playbook_execution_overview_by_activity_id", {"activity_id": activity_id})
        if result:
            data = json.loads(result)
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
            print("   ❌ 工具调用失败")
        
        print("\n" + "=" * 60)
        print("✅ 所有新增MCP工具测试完成!")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_new_mcp_tools())