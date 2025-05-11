# MCP Chat Insight Server

[![English](https://img.shields.io/badge/English-Click-yellow)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-点击查看-orange)](README-zh.md)

## Introduction
MCP WX Insight Server is an MCP server for data analytics. It provides data interaction and business intelligence features via MySQL. The server supports running SQL queries, analyzing business data, and automatically generating business insight memos. It supports both single-database and cross-database analysis modes, which is especially useful when analyzing multiple tables with identical DDLs (e.g., sharded group chat message tables). The server only requires read access for analysis; write and delete operations are not within scope. Please ensure your data is prepared in MySQL before use.

Main features include:
- Support for single-database and cross-database analysis (cross-database requires identical table structures; ensure the DB account can execute `SHOW CREATE TABLE`)
- Supports STDIO and SSE transport protocols (can be debugged with Postman for MCP protocol)
- Complete data validation and error handling
- Debug logging support

## Components

### Resources
The server provides a dynamic resource:
- `memo://business_insights`: A continuously updated business insight memo, summarizing insights discovered during analysis
  - Automatically updated when new insights are found via the append-insight tool

### Prompts
- `chatinsight`: Interactive demo prompt guiding users through database query operations
  - Required parameters: `topic`, `role` – the business domain and user role for analysis
  - Guides users through analysis and business insight discovery

- `chatinsight_ordinary`: Built-in fallback system prompt
  - Used when a system prompt is needed (different from demo prompts)

### Tools

#### Query Tools
- `query`
   - Executes SELECT queries to read data from the database
   - Input:
     - `query` (string): The SELECT SQL query to execute
   - Returns: Query results as an array of objects

- `list_tables`
   - Retrieves the list of active data tables
   - No input required
   - Returns: Query results as an array of objects

#### Analysis Tools
- `append_insight` (deprecated)
   - Adds new business insights to the memo resource
   - Input:
     - `insight` (string): Business insight discovered from data analysis
   - Returns: Confirmation of insight addition
   - Triggers update of the memo://business_insights resource
- `report`
   - Generates a summary report for a custom time range
   - No input required
   - Returns: Guidance prompt for generating the report

## Using with Desktop

### SSE
```bash
# Startup command
$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table "test1.wx_record,test2.wx_record" --desc "Group chat messages" --mapping "chat_data.group_messages" --transport "sse" --port 8000 --sse_path "/mcp-chat-insight/sse" --debug
# Desktop configuration
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
            "test1.wx_record,test2.wx_record", # Table names to analyze (e.g., test.wx_record; use comma to separate multiple tables)
            "--mapping", # Virtual table name for simplifying multi-table SQL generation
            "chat_data.group_messages",
            "--debug" # Run in debug mode
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
# Add the server to your claude_desktop_config.json
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

## Build

### Install Packages

```bash
# Create virtual environment
uv venv --python "D:\software\python3.11\python.exe" .venv
# Activate virtual environment
.\.venv\Scripts\activate
# Install package
uv add fastmcp # uv remove fastmcp
```

### Run

```bash
# Install project dependencies
uv pip install -e .
# Run the service
uv run mcp-chat-insight
```

### Test
```bash
$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table 'test1.wx_record,test2.wx_record' --desc "Group chat messages" --mapping "chat_data.group_messages" --debug

$env:MYSQL_HOST="localhost"; $env:MYSQL_PORT="3306"; $env:MYSQL_USER="root"; $env:MYSQL_PASSWORD="123456"; uv run mcp-chat-insight --table 'test1.wx_record,test2.wx_record' --desc "Group chat messages" --mapping "chat_data.group_messages" --transport "sse" --port 8000 --sse_path "/mcp-chat-insight/sse" --debug # http://localhost:8000/mcp-chat-insight/sse
```

### Packaging & Release

```bash
del /f /q dist\*.*
uv pip install build
python -m build
twine upload -r nexus dist\*
```

## Database Setup

Before running the project, you need to set up the database. A sample schema file is provided at `examples/sample_schema.sql`. This file contains the basic table structure, which you can modify as needed.

To use the sample schema:

1. Install MySQL database
2. Import the sample data into your database tables

Sample schema includes the following tables:
- test1.wx_record: Group chat message table
- test2.wx_record: Group chat message table

## Test MCP Server with MCP Inspector

```bash
uv add "mcp[cli]"
mcp dev src/mcp_chat_insight/server.py:ChatInsightServer
```

## License

This MCP server is licensed under the Apache License 2.0. You are free to use, modify, and distribute this software, provided you comply with the terms and conditions of the Apache License. For more details, see the LICENSE file in the project repository.
