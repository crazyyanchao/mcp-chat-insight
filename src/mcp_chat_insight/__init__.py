#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Author: Yc-Ma
Desc: MCP Chat Insight - A Model Context Protocol server for chat data analysis
Time: 2025-05-04 19:00:00
"""

from . import server
import asyncio
import argparse
import json
from typing import Union, List, Optional
import sys
import logging

def setup_debug_logging():
    """设置调试日志配置。"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def validate_table_name(table_name: str, logger=None) -> list[str]:
    """验证表名并返回数据库名和表名。
    
    Args:
        table_name: 表名，'db.table' 格式，传入多个时请用英文逗号分隔，例如：test1.wx_record,test2.wx_record
        logger: 可选的日志记录器
        
    Returns:
        list[str]: 验证后的表名列表，格式为 ['db.table', ...]
        
    Raises:
        ValueError: 当表名格式无效时
    """
    if logger:
        logger.debug(f"正在验证表名: {table_name}")
    
    if not isinstance(table_name, str):
        raise ValueError("表名必须是字符串类型")
    
    table_name = table_name.strip()
    if not table_name:
        raise ValueError("表名不能为空")
    
    # 分割多个表名
    table_names = [name.strip() for name in table_name.split(',')]
    if not table_names:
        raise ValueError("至少需要提供一个表名")
    
    validated_tables = []
    for full_table_name in table_names:
        if not full_table_name:
            raise ValueError("表名不能为空")
            
        # 处理可能的数据库名.表名格式
        parts = full_table_name.split('.')
        if len(parts) > 2:
            raise ValueError(f"表名格式无效: {full_table_name}，应为 'db.table' 格式")
        
        # 验证表名格式
        if len(parts) == 2:
            db_name, table = parts
            if not db_name.strip():
                raise ValueError(f"数据库名不能为空: {full_table_name}")
            if not table.strip():
                raise ValueError(f"表名不能为空: {full_table_name}")
            db_name = db_name.strip()
            table = table.strip()
            validated_name = f"{db_name}.{table}"
        else:
            table = full_table_name
            validated_name = table
        
        # 验证表名字符
        if not all(c.isalnum() or c in '_' for c in table):
            raise ValueError(f"表名只能包含字母、数字和下划线: {table}")
        
        validated_tables.append(validated_name)
    
    if logger:
        logger.debug(f"验证成功。表名列表: {validated_tables}")
    
    return validated_tables

def validate_mapping_name(mapping_name: str, logger=None) -> str:
    """验证映射表名是否符合MySQL规范。
    
    Args:
        mapping_name: 映射表名，'db.table' 格式
        logger: 可选的日志记录器
        
    Returns:
        str: 验证后的映射表名
        
    Raises:
        ValueError: 当映射表名格式无效时
    """
    if logger:
        logger.debug(f"正在验证映射表名: {mapping_name}")
    
    if not isinstance(mapping_name, str):
        raise ValueError("映射表名必须是字符串类型")
    
    mapping_name = mapping_name.strip()
    if not mapping_name:
        raise ValueError("映射表名不能为空")
    
    # 验证是否只包含一个点号
    if mapping_name.count('.') != 1:
        raise ValueError("映射表名必须且只能包含一个点号，格式为 'db.table'")
    
    # 分割数据库名和表名
    db_name, table_name = mapping_name.split('.')
    
    # 验证数据库名
    if not db_name.strip():
        raise ValueError("数据库名不能为空")
    if not all(c.isalnum() or c in '_' for c in db_name):
        raise ValueError("数据库名只能包含字母、数字和下划线")
    if len(db_name) > 64:  # MySQL数据库名最大长度为64
        raise ValueError("数据库名长度不能超过64个字符")
    
    # 验证表名
    if not table_name.strip():
        raise ValueError("表名不能为空")
    if not all(c.isalnum() or c in '_' for c in table_name):
        raise ValueError("表名只能包含字母、数字和下划线")
    if len(table_name) > 64:  # MySQL表名最大长度为64
        raise ValueError("表名长度不能超过64个字符")
    
    validated_name = f"{db_name.strip()}.{table_name.strip()}"
    
    if logger:
        logger.debug(f"验证成功。映射表名: {validated_name}")
    
    return validated_name

def main():
    """包的主入口点。"""
    parser = argparse.ArgumentParser(
        description='MCP WX ChatInsight - 一个用于微信数据分析的模型上下文协议服务器',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--table',
        type=str,
        required=True,
        help='要分析的表名（例如：test.wx_record，传入多个时请用英文逗号分隔）'
    )

    parser.add_argument(
        '--mapping',
        type=str,
        default="chat_db.group_messages",
        help='映射表名（默认：chat_db.group_messages）'
    )

    parser.add_argument(
        '--desc',
        type=str,
        default="",
        help='要分析的表数据含义说明'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式，显示详细日志'
    )

    parser.add_argument(
        '--transport',
        type=str,
        choices=['stdio', 'sse'],
        default='stdio',
        help='传输模式: stdio 或 sse'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='SSE模式的端口号（默认：8000）'
    )

    parser.add_argument(
        '--sse_path',
        type=str,
        default='/mcp-wx-chatinsight/sse',
        help='SSE端点路径（默认：/mcp-wx-chatinsight/sse）'
    )

    try:
        args = parser.parse_args()
        
        # 如果启用调试模式，设置日志
        logger = setup_debug_logging() if args.debug else None
        if logger:
            logger.debug("已启用调试模式")
            logger.debug(f"参数: table={args.table}, transport={args.transport}, port={args.port}, sse_path={args.sse_path}")
        
        # 验证表名
        table_names = validate_table_name(args.table, logger)
        
        # 验证映射表名
        mapping_name = validate_mapping_name(args.mapping, logger)
        
        # 使用SSE模式时验证端口和sse_path
        if args.transport == 'sse':
            if not 1024 <= args.port <= 65535:
                raise ValueError("端口必须在1024到65535之间")
            if not args.sse_path.startswith('/'):
                raise ValueError("SSE路径必须以'/'开头")
            if not args.sse_path.endswith('/sse'):
                raise ValueError("SSE路径必须以'/sse'结尾")
        
        if logger:
            logger.debug("正在使用以下配置启动服务器:")
            logger.debug(f"表: {table_names}")
            logger.debug(f"传输: {args.transport}")
            if args.transport == 'sse':
                logger.debug(f"端口: {args.port}")
                logger.debug(f"SSE路径: {args.sse_path}")
        
        # 使用验证后的配置运行服务器
        asyncio.run(server.main(
            table_names=table_names,
            desc=args.desc,
            transport=args.transport,
            port=args.port,
            sse_path=args.sse_path,
            mapping=mapping_name
        ))
        
    except ValueError as e:
        error_msg = f"错误: {str(e)}"
        if logger:
            logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_msg = f"意外错误: {str(e)}"
        if logger:
            logger.error(error_msg, exc_info=True)
        print(error_msg, file=sys.stderr)
        sys.exit(1)

# 可选：在包级别暴露其他重要项
__all__ = ['main', 'server']

