# MCP Chat Insight Server

[![English](https://img.shields.io/badge/English-Click-yellow)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-点击查看-orange)](README-zh.md)

## 简介
MCP WX Insight Server 是一个用于数据分析的 MCP 服务器。通过 MySQL 提供数据交互和商业智能功能。该服务器支持运行 SQL 查询、分析业务数据，并自动生成业务洞察备忘录。支持单库和跨库分析模式。当有多个DDL相同的表需要进行分析时非常有用（例如群聊消息分库分表存储，需要分析时非常有用）。该 MCP 服务器仅需要读取分析数据，所以写入删除等操作工具不在讨论范围以内，使用时请提前在 MySQL 中准备好数据。

主要功能包括：
- 支持单库和跨库分析模式（跨库需要保证表结构一致）（确保数据库账号可以执行`SHOW CREATE TABLE`）
- 支持 STDIO 和 SSE 传输协议（可分别用Postman进行MCP协议的调试）
- 提供完整的数据验证和错误处理
- 支持调试日志记录

## 组件

### 资源
服务器提供了一个动态资源：
- `memo://business_insights`：一个持续更新的业务洞察备忘录，用于汇总分析过程中发现的洞察
  - 通过 append-insight 工具发现新的洞察时自动更新

### 提示
- `chatinsight`：交互式演示提示，引导用户完成数据库查询操作
  - 必需参数：`topic` `role` - 要分析的业务领域和用户角色设定
  - 引导用户完成分析和业务洞察

- `chatinsight_ordinary`：内置的备用系统提示词
  - 在需要系统提示词时使用（区别于演示提示词）

### 工具

#### 查询工具
- `query`
   - 执行 SELECT 查询以从数据库读取数据
   - 输入：
     - `query`（字符串）：要执行的 SELECT SQL 查询
   - 返回：查询结果作为对象数组

- `list_tables`
   - 获取实际在用的数据表列表
   - 不需要输入
   - 返回：查询结果作为对象数组

#### 分析工具
- `append_insight`（停用）
   - 向备忘录资源添加新的业务洞察
   - 输入：
     - `insight`（字符串）：从数据分析中发现的业务洞察
   - 返回：洞察添加确认
   - 触发 memo://business_insights 资源更新
- `report`
   - 生成自定义时间范围的数据总结报告
   - 不需要输入
   - 返回：生成报告的指导提示词

## 与 Desktop 一起使用

### SSE
```bash
# 启动命令
$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table "test1.wx_record,test2.wx_record" --desc "微信群聊消息" --mapping "chat_data.group_messages" --transport "sse" --port 8000 --sse_path "/mcp-chat-insight/sse" --debug
# 在桌面端配置
{
    "mcp-chat-insight":
    {
        "type": "sse",
        "command": "http://localhost:8000/mcp-chat-insight/sse"
    }
}
```

### STDIO
```bash
{
    "mcp-chat-insight":
    {
        "command": "uv",
        "args":
        [
            "--directory",
            "parent_of_servers_repo/.../mcp_chat_insight",
            "run",
            "mcp-chat-insight",
            "--table",
            "test1.wx_record,test2.wx_record", # 要分析的表名（例如：test.wx_record，传入多个时请用英文逗号分隔）
            "--mapping", # 可见的虚拟表名，用于降低多表SQL生成的复杂性
            "chat_data.group_messages",
            "--debug" # Debug模式下运行
        ],
        "env":
        {
            "MYSQL_HOST": "localhost",
            "MYSQL_PORT": "3306",
            "MYSQL_USER": "root",
            "MYSQL_PASSWORD": "123456"
        }
    }
}
```

```bash
# Claude
{
  "mcp-chat-insight": {
    "command": "npx",
    "args": [
    "-y",
    "supergateway",
    "--sse",
    "http://localhost:8000/mcp-chat-insight/sse"
  ]
}
```

### Docker

```json
# 将服务器添加到您的 claude_desktop_config.json
"mcpServers": {
  "mcp-chat-insight": {
    "command": "docker",
    "args": [
      "run",
      "--rm",
      "-i",
      "-v",
      "mcp-test:/mcp",
      "mcp/mcp-chat-insight",
      "--table",
      "..."
    ]
  }
}
```

## 构建

### 安装包

```bash
# 创建虚拟环境
uv venv --python "D:\software\python3.11\python.exe" .venv
# 激活虚拟环境
.\.venv\Scripts\activate
# 安装包
uv add fastmcp # uv remove fastmcp
```

### 运行

```bash
# 安装项目依赖
uv pip install -e .
# 运行服务
uv run mcp-chat-insight
```

### 测试
```bash
$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table 'test1.wx_record,test2.wx_record' --desc "微信群聊消息" --mapping "chat_data.group_messages" --debug

$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table 'test1.wx_record,test2.wx_record' --desc "微信群聊消息" --mapping "chat_data.group_messages" --transport "sse" --port 8000 --sse_path "/mcp-chat-insight/sse" --debug # http://localhost:8000/mcp-chat-insight/sse
```

### 打包发布

```bash
del /f /q dist\*.*
uv pip install build
python -m build
twine upload -r nexus dist\*
```

## 数据库设置

在运行项目之前，您需要设置数据库。我们提供了一个示例数据库模式文件，位于 `examples/sample_schema.sql`。这个文件包含了基本的表结构，您可以根据需要进行修改。

要使用示例数据库模式：

1. 安装MySQL数据库
2. 并将示例数据写入到库表中

示例模式包含以下表：
- test1.wx_record：群聊消息表
- test2.wx_record：群聊消息表

## 使用 MCP inspector 测试 MCP Server

```bash
uv add "mcp[cli]"
mcp dev src/mcp_chat_insight/server.py:ChatInsightServer
```

## 许可证

本 MCP 服务器采用 Apache 许可证 2.0 版本。这意味着您可以自由使用、修改和分发该软件，但需遵守 Apache 许可证的条款和条件。有关更多详细信息，请参阅项目存储库中的 LICENSE 文件。
