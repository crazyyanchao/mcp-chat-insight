#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Author: Yc-Ma
Desc: Server implementation for MCP Chat Insight
Time: 2024-03-21 00:00:00
"""

import os
import sys
import logging
from typing import Union, List, Dict, Any
import aiomysql
from fastmcp import FastMCP
import mcp.types as types
from pydantic import Field
import asyncio
import re

from mcp_chat_insight.prompt import PROMPT_TEMPLATE, PROMPT_TEMPLATE_GUIDANCE, PROMPT_TEMPLATE_REPORT

# 重新配置 Windows 系统下的默认编码（从 windows-1252 改为 utf-8）
if sys.platform == "win32" and os.environ.get('PYTHONIOENCODING') is None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger('mcp_wx_chatinsight')
logger.info("Starting MCP WX ChatInsight Server")

class DatabaseConfig:
    def __init__(self):
        self.host = os.getenv('MYSQL_HOST', 'localhost')
        self.port = int(os.getenv('MYSQL_PORT', '3306'))
        self.user = os.getenv('MYSQL_USER', 'root')
        self.password = os.getenv('MYSQL_PASSWORD', '')
        self.default_db = os.getenv('MYSQL_DATABASE', '')

class DatabaseManager:
    def __init__(self, table_names: List[str], mapping: str, desc: str = ""):
        self.config = DatabaseConfig()
        self.pools: Dict[str, aiomysql.Pool] = {}
        self.insights: list[str] = []
        self.table_names = table_names
        self.mapping = mapping
        self.desc = desc
        self.ddl_file = '_chat_insight_ddl.txt'
    
    async def __call__(self, *args: Any, **kwds: Any) -> Any:
        # 初始化数据库连接
        for table_name in self.table_names:
            await self.get_pool(table_name)
            
        # 写入DDL到文件
        with open(self.ddl_file, 'w', encoding='utf-8') as f:
            f.write(await self.ddl())
        logger.debug(f"DDL文件已写入 {self.ddl_file}: {self.read_ddl()}")

    async def get_pool(self, table_name: str) -> aiomysql.Pool:
        if '.' in table_name:
            db_name = table_name.split('.')[0]
        else:
            raise ValueError(f"表名格式错误，请使用 db_name.table_name 格式")
        if db_name not in self.pools:
            self.pools[db_name] = await aiomysql.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            db=db_name,
            autocommit=True
        )
        return self.pools[db_name]

    async def close(self):
        for pool in self.pools.values():
            pool.close()
            await pool.wait_closed()
    
    async def _synthesize_memo(self) -> str:
        """将业务洞察合成为格式化的备忘录"""
        logger.debug(f"正在合成包含 {len(self.insights)} 条洞察的备忘录")
        if not self.insights:
            return "目前尚未发现任何业务洞察。"

        insights = "\n".join(f"- {insight}" for insight in self.insights)

        memo = "📊 业务洞察备忘录 📊\n\n"
        memo += "关键洞察发现：\n\n"
        memo += insights

        if len(self.insights) > 1:
            memo += "\n总结：\n"
            memo += f"分析揭示了{len(self.insights)}个关键业务洞察，这些洞察为业务战略优化和增长提供了机会。"

        logger.debug("已生成基础备忘录格式")
        return memo
    
    async def describe_table(self) -> str:
        """获取数据表的详细表结构（DDL）信息。"""
        columns = []
        # 获取任意一个表的结构信息即可
        pool = await self.get_pool(self.table_names[0])  # 使用第一个数据库
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"SHOW CREATE TABLE {self.table_names[0]}")
                db_columns = await cur.fetchall()
                columns.extend(db_columns)
        prefix = f"表 {self.mapping} 的结构信息如下：\n"
        return prefix + "".join(f"{column['Create Table']}\n" for column in columns)
    
    async def ddl(self) -> str:
        """获取数据表的详细表结构（DDL）信息。"""
        return await self.describe_table()
    
    def read_ddl(self) -> str:
        """读取DDL文件内容（使用文件读取DDL，避免同步异步操作的冲突）。"""
        with open(self.ddl_file, 'r', encoding='utf-8') as f:
            return f.read()
        
    def rewrite_sql(self, query: str) -> str:
        """重写SQL查询语句，将SQL中表名<chat_db.group_messages>替换为真实表名。
        1. 去掉当前SQL结尾的`;`
        2. 将SQL中<db_name.table_name>设置为真实表名，多个表使用`UNION ALL`连接
        """
        # 去掉SQL结尾的分号
        query = query.rstrip(';')
            
        # 如果只有一个表，直接替换表名
        if len(self.table_names) == 1:
            return query.replace(self.mapping, self.table_names[0])
            
        # 处理多个表的情况
        subqueries = []
        for table_name in self.table_names:
            # 替换表名并添加括号
            subquery = query.replace(self.mapping, table_name)
            subqueries.append(f"({subquery})")
            
        # 用 UNION ALL 连接所有子查询
        final_sql = " UNION ALL ".join(subqueries) + ";"
        logger.debug(f"重写SQL: {final_sql}")
        return final_sql
    
    def tool_query_description(self) -> str:
        """提供给`query`工具的描述信息"""
        desc_text = f"这些表存储的主要数据内容是{self.desc}。" if self.desc else ""
        return f"""
                {desc_text}
            Args:
                query (str): MySQL SQL SELECT 查询语句。格式要求：
                    - 必须以 SELECT 开头，表名为 {self.mapping}
                    - 表结构信息：{self.read_ddl()}
            """


class ChatInsightServer:
    def __init__(self, db_manager: DatabaseManager, table_names: List[str], desc: str = "", mapping: str = "chat_db.group_messages", sse_path: str = "/mcp-chat-insight/sse"):
        self.table_names = table_names # [db1.table,db2.table...] 格式
        self.mapping = mapping
        self.desc = desc
        self.db_manager = db_manager
        
        self.mcp = FastMCP(name="mcp-chat-insight", sse_path=sse_path)
        self._register_tools()

    def _register_tools(self):
        
        @self.mcp.resource(uri='memo://business_insights', name='业务洞察备忘录', description='记录已发现的业务洞察的动态文档', mime_type='text/plain')
        async def resource() -> str:
            return await self.db_manager._synthesize_memo()

        # @self.mcp.prompt(name='chatinsight',
        #                  description='一个提示词，用于初始化数据库并演示用什么角色使用 MySQL MCP 服务器 + LLM')
        # async def prompt(topic: str = Field(description="用于初始化数据库的初始数据主题",required=True),
        #                  role: str = Field(description="用于初始化数据库的数据分析角色",required=True)) -> types.GetPromptResult:
        #     logger.debug(f"处理获取提示请求，主题: {topic}，角色: {role}")
        #     prompt = PROMPT_TEMPLATE.format(topic=topic,role=role)

        #     logger.debug(f"为主题: {topic} 和角色: {role} 生成了提示模板")
        #     return types.GetPromptResult(
        #         description=f"用于主题 {topic} 和角色 {role} 的示例模板",
        #         messages=[
        #         types.PromptMessage(role="user",content=types.TextContent(type="text", text=prompt.strip()))])
        
        @self.mcp.prompt(name='chatinsight',
                         description='一个提示词，用于初始化数据库并演示用什么角色使用 MySQL MCP 服务器 + LLM')
        async def prompt(topic: str = Field(description="用于初始化数据库的初始数据主题",required=True),
                         role: str = Field(description="用于初始化数据库的数据分析角色",required=True)) -> str:
            logger.debug(f"处理获取提示请求，主题: {topic}，角色: {role}")
            prompt = PROMPT_TEMPLATE_GUIDANCE.format(topic=topic,role=role)

            logger.debug(f"为主题: {topic} 和角色: {role} 生成了提示模板")
            return prompt.strip()
        
        @self.mcp.prompt(name='chatinsight_ordinary',
                         description='一个提示词，用于填充系统提示词')
        async def prompt_ordinary() -> str:
            return PROMPT_TEMPLATE
        
        @self.mcp.tool(description=f"""对数据表 {self.mapping} 执行 SQL SELECT 查询并返回结果。
                    {self.db_manager.tool_query_description()}""")
        async def query(query: str) -> List[Dict[str, Any]]:
            cr_queryh = re.sub(r'[^a-zA-Z]', '', query)
            if not cr_queryh.upper().startswith('SELECT'):
                raise ValueError("只允许 SELECT 查询")
            
            try:
                results = []
                query = self.db_manager.rewrite_sql(query)
                pool = await self.db_manager.get_pool(self.table_names[0])
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(query)
                        db_results = await cur.fetchall()
                        results.extend(db_results)
                return results
            except Exception as e:
                logger.error(f"Error executing query: {str(e)}")
                raise
        
        @self.mcp.tool(description="获取实际使用的数据表列表")
        async def list_tables() -> Dict[str, Union[str, List[str]]]:
            """返回当前配置的实际数据表列表。
            """
            desc_text = f"数据查询时，使用此表：{self.mapping}，它是{self.table_names}的虚拟聚合表，所有查询都要从{self.mapping}表中查询。"
            return {"description": desc_text, "tables": self.table_names}
        
        @self.mcp.tool()
        async def report() -> str:
            """当用户需要生成群聊消息的日报、周报、月报等时，先使用该工具获取相关提示词，用于指导下一步操作。
            """
            return PROMPT_TEMPLATE_REPORT.format(desc=self.desc)

        # @self.mcp.tool()
        # async def append_insight(insight: str) -> Dict[str, str]:
        #     """添加新的业务洞察记录到系统中。

        #     该工具用于在数据分析过程中收集和记录重要的业务发现，帮助用户更好地理解和利用数据中的洞察。
        #     添加的洞察会被自动整合到系统备忘录中，并实时通知客户端更新。

        #     Args:
        #         insight (str): 业务洞察内容，应包含对数据的分析和见解。例如："本月用户活跃度较上月提升20%"
        #     """
        #     # 添加洞察的实现
        #     self.db_manager.insights.append(insight)
        #     await self.db_manager._synthesize_memo()

        #     # 通知客户端备忘录资源已更新
        #     await self.mcp.get_context().session.send_resource_updated(AnyUrl("memo://insights"))

        #     return [types.TextContent(type="text", text="洞察已添加到备忘录")]

    async def start(self, transport: str = "stdio", port: int = 8000):
        """启动服务器。"""
        try:
            # 使用指定的传输方式启动 MCP 服务器
            if transport == "sse":
                await self.mcp.run_async(transport="sse", host="0.0.0.0", port=port)
            else:  # stdio
                await self.mcp.run_async(transport="stdio")
        finally:
            # 清理数据库连接
            await self.db_manager.close()

async def main(table_names: List[str], desc: str = "chat_db.group_messages", mapping: str = "", transport: str = "stdio", port: int = 8000, sse_path: str = "/mcp-chat-insight/sse"):
    """服务器的主入口点。"""
    db_manager = DatabaseManager(table_names,mapping,desc)
    await db_manager()
    server = ChatInsightServer(db_manager, table_names, desc, mapping, sse_path)
    await server.start(transport, port)

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="MCP WX ChatInsight")
    # parser.add_argument("--port", type=int, default=8000, help="端口")
    # args = parser.parse_args()
    # main(args)
    # mcp.run(transport="sse", host="0.0.0.0", port=8000) # http://localhost:8000/mcp-chat-insight/sse # sse_path="/mcp-chat-insight/sse"
    # mcp.run(transport="stdio")
    os.environ["MYSQL_HOST"] = "localhost"
    os.environ["MYSQL_PORT"] = "3306"
    os.environ["MYSQL_USER"] = "root"
    os.environ["MYSQL_PASSWORD"] = "123456"
    main(table_names=["test1.wx_record","test2.wx_record"], desc="微信群聊数据")

