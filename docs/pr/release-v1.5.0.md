# SOAR MCP Server v1.5.0 发布：让 AI 更安全地调度安全编排

> 从密码哈希到 Bearer Token，八个版本迭代，一次安全与体验的全面进化。

---

## 写在前面

过去几个版本，我们对 SOAR MCP Server 进行了一次从内到外的系统性升级。从 v1.1.0 的安全加固，到 v1.2.0 的异步架构重构，再到 v1.4.0 的前端 UI 焕新，直至今天 v1.5.0 的 **HTTP Bearer Token 双模式认证** —— 每一步都在回答同一个问题：

**如何让 AI 更安全、更高效地调度企业安全编排能力？**

本文将带你快速了解这八个版本中最值得关注的变化。

---

## 一、安全加固：从地基开始（v1.1.0 ~ v1.1.1）

安全产品的基座必须首先是安全的。这两个版本聚焦于认证和网络层面的加固。

### 密码安全升级

旧版使用 SHA-256 做密码哈希，存在彩虹表攻击风险。新版全面切换到 **bcrypt**（带盐哈希），每个密码的哈希结果都不同，即使两个用户使用相同密码。

### JWT 密钥持久化

之前每次重启服务器都会重新生成 JWT 签名密钥，导致所有已登录的管理员会话失效。现在密钥持久化到数据库中，**重启不影响已有会话**。

### 网络安全收紧

- **SSL 验证默认开启** —— 不再跳过证书验证，自签名证书环境可手动关闭
- **服务默认绑定 127.0.0.1** —— 防止意外暴露到公网
- **敏感信息日志脱敏** —— 管理员密码仅在控制台显示一次，不写入日志文件

---

## 二、架构改进：异步化与上下文安全（v1.2.0 ~ v1.2.2）

MCP 工具函数需要调用 SOAR 平台 API，网络 I/O 是主要瓶颈。这一阶段将核心调用链全面异步化。

### 异步工具 + 连接池复用

```
requests (同步, 每次新建连接)
    ↓
httpx.AsyncClient (异步, 共享连接池)
```

所有 MCP 工具函数（`execute_playbook`、`query_playbook_execution_status_by_activity_id` 等）改为 `async`，配合 `httpx.AsyncClient` 共享实例，连接复用，减少 TCP 握手开销。

### contextvars 替代 threading.local

异步环境下 `threading.local` 无法正确隔离协程上下文。切换到 Python 标准库的 `contextvars.ContextVar`，**每个 MCP 请求的用户信息在异步调用链中安全传递**。

### 其他改进

- **有界执行记录**：`BoundedDict` 最多保留 1000 条，LRU 自动淘汰，防止内存无限增长
- **DB Session 上下文管理器**：`@contextmanager` 包装，自动关闭连接，杜绝泄漏
- **密码重置脚本**：升级为 bcrypt v2.0，交互式彩色界面

---

## 三、项目结构优化（v1.3.0）

代码积累到一定阶段后，是时候做一次"大扫除"了。

- 模板文件迁移到 `templates/` 目录
- 文档归档到 `docs/archive/`
- 截图整理到 `docs/images/`
- 清理生成脚本、临时文件等历史遗留

目录结构规范化后，新贡献者可以更快理解项目布局。

---

## 四、前端 UI 全面重构（v1.4.0）

管理后台从"能用"升级到"好用"。

### Cyber Shield 设计系统

全新的暗色主题设计语言，专为安全运营场景打造。表格、卡片、弹窗、状态标签等组件统一风格。

### Google Fonts 本地化

将 `Plus Jakarta Sans` 和 `JetBrains Mono` 字体文件内嵌到项目中，**内网环境无需访问 Google 服务器**即可正常渲染。

### 剧本详情优化

剧本详情弹框重新设计布局，参数定义、执行状态等信息层次更清晰。

---

## 五、MCP 认证增强：Bearer Token 双模式（v1.5.0）

这是本次发布的重头戏。

### 为什么需要 Bearer Token？

之前 MCP 客户端连接服务器时，Token 放在 URL 查询参数中：

```
http://127.0.0.1:12345/mcp?token=XUVghOvZ3AED...
```

这种方式有一个隐患 —— **Token 会出现在浏览器历史记录、代理服务器日志、Nginx 访问日志、HTTP Referer 头中**。

v1.5.0 新增 **HTTP Bearer Token** 认证方式：

```
Authorization: Bearer XUVghOvZ3AED...
```

Token 放在 HTTP Header 中，不会被 URL 日志记录，安全性显著提升。

### 双模式并存，零迁移成本

我们采用**"Bearer 优先，URL 兼容"**的策略：

```
请求到达
  │
  ├─ 检查 Authorization: Bearer <token>  ← 优先
  │
  ├─ 检查 ?token=<token>                 ← 兼容 fallback
  │
  └─ 两者都没有 → 401 拒绝
```

**现有的 MCP 客户端配置完全不需要修改**。支持 Bearer Token 的客户端可以随时切换到更安全的方式。

### MCP 客户端配置示例

**URL 参数（兼容方式）：**
```json
{
  "mcpServers": {
    "soar-mcp": {
      "url": "http://127.0.0.1:12345/mcp?token=xxxx"
    }
  }
}
```

**Bearer Token（推荐方式）：**
```json
{
  "mcpServers": {
    "soar-mcp": {
      "url": "http://127.0.0.1:12345/mcp",
      "headers": {
        "Authorization": "Bearer xxxx"
      }
    }
  }
}
```

### Token 管理体验优化

创建 Token 后的弹窗也进行了重构：

- **等宽字体** 展示 Token / URL / Bearer Header，一目了然
- 每个字段带 **内联复制按钮**，点击后显示 ✅ 已复制的动效反馈
- 新增 **"一键复制全部"** 按钮，三项信息一次到手
- **HTTP 认证头字段**（`Authorization: Bearer <token>`）直接展示，方便复制到 HTTP 客户端

### 状态标签优化

Token 列表的状态标签从纯文字升级为 Pill 药丸样式：

- 🟢 **活跃** —— 绿底绿字
- ⚪ **已禁用** —— 灰底灰字
- 🔴 **已过期** —— 红底红字

---

## 六、测试覆盖

v1.5.0 新增了完整的认证测试套件 `tests/test_bearer_auth.py`：

**15 个单元测试**，覆盖：
- Token 验证：有效 / 无效 / 过期 / 空值 / 数据库异常
- Bearer 头提取与解析
- URL 查询参数提取
- Bearer 优先于 URL 参数的优先级
- Authorization 头大小写不敏感
- 错误格式（Basic / 空值 / 错误前缀）拒绝

**集成测试**，覆盖：
- Bearer Token 访问 MCP 端点 → 200
- URL 参数访问 MCP 端点 → 200
- 无认证请求 → 401
- 无效 Token → 401

```bash
# 只跑单元测试（无需启动服务器）
python tests/test_bearer_auth.py --unit-only

# 跑完整测试（需要服务器运行）
python tests/test_bearer_auth.py --token <your_token>
```

---

## 升级指南

### 从 v1.4.0 升级

```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python3 soar_mcp_server.py
```

升级是平滑的：
- 现有 Token 和配置自动保留
- 现有 MCP 客户端无需修改配置
- Bearer Token 是新增能力，可选使用

### 从 v1.0.x 升级

需要额外重置管理员密码（SHA-256 → bcrypt 不兼容）：

```bash
./reset_admin_password.sh --random
```

---

## 版本历程一览

| 版本 | 主题 | 核心关键词 |
|------|------|-----------|
| v1.1.0 | 安全加固 | bcrypt、JWT 持久化、日志脱敏 |
| v1.1.1 | 安全加固 | SSL 验证、127.0.0.1 绑定、竞态修复 |
| v1.2.0 | 架构改进 | httpx 异步、contextvars、有界字典 |
| v1.2.1 | 代码质量 | 模块修复、日志轮转、依赖清理 |
| v1.2.2 | 工具升级 | bcrypt 脚本、文档更新 |
| v1.3.0 | 项目优化 | 目录规范、文档归档 |
| v1.4.0 | UI 重构 | Cyber Shield 设计、字体本地化 |
| **v1.5.0** | **认证增强** | **Bearer Token、双模式认证、测试套件** |

---

## 下一步

- SSE 传输支持（Server-Sent Events）
- Token 权限细粒度控制（按工具/资源授权）
- 执行历史可视化和统计面板
- 多 SOAR 平台实例管理

---

## 关于项目

**SOAR MCP Server** 基于 [OctoMation SOAR 平台](https://github.com/flagify-com/OctoMation) 构建，通过 Model Context Protocol 将安全编排能力集成到 Claude Desktop、Cherry Studio、Cursor 等 AI 客户端中。

- GitHub: https://github.com/flagify-com/soar-mcp
- OctoMation: https://github.com/flagify-com/OctoMation

---

*雾帜智能 · 用 AI 赋能网络安全*
