# 测试数据库表注释提取功能
import os
import sys

# 清除代理环境变量
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(var, None)
os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"

import logging
from backend.app.test_agent import fetch_table_definitions_with_comments
from backend.app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """测试提取数据库表结构和注释"""
    logger.info("=" * 80)
    logger.info("开始测试数据库表注释提取功能")
    logger.info("=" * 80)
    
    # 提取表定义
    table_defs = fetch_table_definitions_with_comments(settings.rollerbed_database_url)
    
    if not table_defs:
        logger.error("❌ 未能提取任何表定义")
        return
    
    logger.info(f"\n✅ 成功提取 {len(table_defs)} 个表的定义\n")
    
    # 打印每个表的定义
    for table_name, definition in table_defs.items():
        print("=" * 80)
        print(f"表名: {table_name}")
        print("=" * 80)
        print(definition)
        print("\n")
    
    # 检查是否包含注释
    has_comments = False
    for definition in table_defs.values():
        if "-- Description:" in definition or " -- " in definition:
            has_comments = True
            break
    
    if has_comments:
        logger.info("✅ 检测到表或字段包含注释信息")
    else:
        logger.warning("⚠️  未检测到注释信息，请检查数据库表是否有 COMMENT")

if __name__ == "__main__":
    main()
