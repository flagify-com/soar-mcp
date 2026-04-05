#!/usr/bin/env python3
"""
Unit tests for playbook result overview and key result extraction.
"""

import os
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from models import DatabaseManager, PlaybookData
from migrate_db import run_migration
from soar_mcp_server import (
    _build_focused_execution_result,
    _build_simple_execution_result,
    _match_focus_nodes,
    admin_app,
    mcp,
)
from version import __version__


SAMPLE_API_RESULT = {
    "code": 200,
    "result": {
        "activity": {
            "activityId": "activity-demo-001",
            "playbookId": 1907203516548373,
            "displayName": "暴力破解处置剧本_云上",
            "excuteStatus": "SUCCESS",
            "createTime": "2026-04-05 15:59:04",
            "finishTime": "2026-04-05 16:02:25",
            "excutorActionParams": [{"key": "src", "value": "66.240.205.34"}],
        },
        "nodeResultModels": [
            {
                "id": 101,
                "nodeId": "node-ti",
                "displayName": "查询威胁情报",
                "nodeType": "ACTION",
                "appDisplayName": "山石云瞻-威胁情报",
                "actionDisplayName": "高级威胁查询：IP",
                "excuteStatus": "SUCCESS",
                "code": 200,
                "msg": "成功",
            },
            {
                "id": 102,
                "nodeId": "node-approve",
                "displayName": "人工审核封禁",
                "nodeType": "APPROVE",
                "excuteStatus": "SUCCESS",
                "code": 200,
                "msg": "审批成功",
            },
            {
                "id": 103,
                "nodeId": "node-isolate",
                "displayName": "云平台安全组隔离",
                "nodeType": "ACTION",
                "appDisplayName": "阿里云客户端工具",
                "actionDisplayName": "将实例加入安全组",
                "excuteStatus": "SUCCESS",
                "code": 200,
                "msg": "成功",
            },
        ],
        "assetResultModels": [
            {
                "id": 1001,
                "nodeResultId": 101,
                "assetName": "SS",
                "status": "SUCCESS",
                "result": {"risk_level": "malicious"},
            },
            {
                "id": 1002,
                "nodeResultId": 103,
                "assetName": "aliyun-a",
                "status": "SUCCESS",
                "result": {"instanceId": "i-001"},
            },
            {
                "id": 1003,
                "nodeResultId": 103,
                "assetName": "aliyun-b",
                "status": "SUCCESS",
                "result": {"instanceId": "i-002"},
            },
        ],
    },
}


class TestPlaybookFocusKeywordStorage(unittest.TestCase):
    """Test keyword normalization, migration, and persistence."""

    def setUp(self):
        fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_manager = DatabaseManager(self.temp_db)
        self.db_manager.init_db()

    def tearDown(self):
        self.db_manager.engine.dispose()
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

    def test_normalize_focus_keywords_supports_comma_newline_and_dedup(self):
        keywords = DatabaseManager._normalize_focus_keywords(" 威胁情报, 隔离，隔离\n审批 ")
        self.assertEqual(keywords, ["威胁情报", "隔离", "审批"])

    def test_update_and_get_focus_keywords_roundtrip(self):
        playbook = PlaybookData(id=123456, name="keyword_test_playbook")
        self.assertTrue(self.db_manager.save_playbook(playbook))

        self.assertTrue(
            self.db_manager.update_playbook_focus_keywords(123456, ["威胁情报", "隔离", "隔离", " "])
        )

        self.assertEqual(
            self.db_manager.get_playbook_focus_keywords(123456),
            ["威胁情报", "隔离"],
        )

        detail = self.db_manager.get_playbook_by_id(123456)
        self.assertEqual(detail["resultFocusKeywords"], ["威胁情报", "隔离"])

    def test_migrate_playbooks_schema_adds_focus_keyword_column(self):
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

        conn = sqlite3.connect(self.temp_db)
        conn.execute(
            """
            CREATE TABLE playbooks (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                playbook_category VARCHAR(100),
                description TEXT,
                create_time DATETIME,
                update_time DATETIME,
                remote_update_time DATETIME,
                playbook_params TEXT,
                sync_time DATETIME,
                enabled BOOLEAN DEFAULT 1
            )
            """
        )
        conn.commit()
        conn.close()

        legacy_db_manager = DatabaseManager(self.temp_db)
        legacy_db_manager.init_db()

        conn = sqlite3.connect(self.temp_db)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(playbooks)").fetchall()]
        conn.close()
        legacy_db_manager.engine.dispose()

        self.assertIn("result_focus_keywords", columns)

    def test_manual_migration_script_reuses_init_db_migration(self):
        if os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

        conn = sqlite3.connect(self.temp_db)
        conn.execute(
            """
            CREATE TABLE playbooks (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                playbook_category VARCHAR(100),
                description TEXT,
                create_time DATETIME,
                update_time DATETIME,
                remote_update_time DATETIME,
                playbook_params TEXT,
                sync_time DATETIME,
                enabled BOOLEAN DEFAULT 1
            )
            """
        )
        conn.commit()
        conn.close()

        summary = run_migration(self.temp_db)

        self.assertTrue(summary["resultFocusKeywordsAdded"])
        self.assertIn("result_focus_keywords", summary["playbookColumnsAfter"])


class TestPlaybookResultViews(unittest.TestCase):
    """Test overview and key result extraction helpers."""

    def test_match_focus_nodes_uses_or_semantics(self):
        matched_nodes = _match_focus_nodes(
            SAMPLE_API_RESULT["result"]["nodeResultModels"],
            ["威胁情报", "隔离"],
        )

        self.assertEqual(len(matched_nodes), 2)
        self.assertEqual(matched_nodes[0]["keywordHits"], ["威胁情报"])
        self.assertEqual(matched_nodes[1]["keywordHits"], ["隔离"])

    def test_build_simple_execution_result_contains_digest_and_asset_counts(self):
        result = _build_simple_execution_result(SAMPLE_API_RESULT, ["威胁情报", "隔离"])

        self.assertEqual(result["activity"]["activityId"], "activity-demo-001")
        self.assertEqual(result["focusKeywordsConfigured"], ["威胁情报", "隔离"])
        self.assertTrue(result["focusedResultAvailable"])
        self.assertEqual(result["counts"]["totalNodes"], 3)
        self.assertEqual(result["counts"]["totalAssetResults"], 3)
        self.assertEqual(result["nodeResultModels"][0]["assetResultCount"], 1)
        self.assertEqual(result["nodeResultModels"][2]["assetResultCount"], 2)

    def test_build_focused_execution_result_filters_nodes_and_assets(self):
        result = _build_focused_execution_result(SAMPLE_API_RESULT, ["威胁情报", "隔离"])

        self.assertTrue(result["keywordConfigured"])
        self.assertEqual(result["keywordMatchMode"], "OR")
        self.assertEqual(result["matchedNodeCount"], 2)
        self.assertEqual(result["matchedAssetCount"], 3)
        self.assertEqual(result["unmatchedNodeCount"], 1)
        self.assertEqual(result["unmatchedAssetCount"], 0)
        self.assertEqual(
            [node["displayName"] for node in result["nodeResultModels"]],
            ["查询威胁情报", "云平台安全组隔离"],
        )
        self.assertEqual(
            [asset["nodeResultId"] for asset in result["assetResultModels"]],
            [101, 103, 103],
        )

    def test_build_focused_execution_result_without_keywords_returns_message(self):
        result = _build_focused_execution_result(SAMPLE_API_RESULT, [])

        self.assertFalse(result["keywordConfigured"])
        self.assertEqual(result["matchedNodeCount"], 0)
        self.assertEqual(result["matchedAssetCount"], 0)
        self.assertIn("未配置结果提取关键词", result["message"])

    def test_mcp_tool_registry_exposes_new_semantic_names(self):
        registered_tools = set(mcp._tool_manager._tools.keys())

        self.assertIn("query_playbook_execution_overview_by_activity_id", registered_tools)
        self.assertIn("query_playbook_execution_key_results_by_activity_id", registered_tools)


class TestAdminVersionDisplay(unittest.TestCase):
    """Test admin page version rendering."""

    def test_admin_page_renders_current_version(self):
        with admin_app.test_client() as client:
            response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn(f"v{__version__}", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
