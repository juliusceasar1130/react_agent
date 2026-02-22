#!/usr/bin/env python3
# backend/app/agent/vector/pgvector_init/import_data.py
"""
向量库数据导入主入口脚本

使用 langchain-postgres 的 PGVector 类实现批量导入功能。

用法:
    python -m backend.app.agent.vector.pgvector_init.import_data <json_file_path> [options]

示例:
    # 基本用法（追加导入）
    python -m backend.app.agent.vector.pgvector_init.import_data data.json

    # 覆盖导入（清空现有数据）
    python -m backend.app.agent.vector.pgvector_init.import_data data.json --overwrite

    # 指定集合名称
    python -m backend.app.agent.vector.pgvector_init.import_data data.json --collection-name my_collection
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.agent.vector.pgvector_init.json_loader import load_json_data
from backend.app.agent.vector.pgvector_init.data_importer import import_data_to_vector_store

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def progress_callback(current: int, total: int):
    """进度回调函数"""
    percentage = (current / total * 100) if total > 0 else 0
    print(f"\r进度: {current}/{total} ({percentage:.1f}%)", end="", flush=True)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将 JSON 数据导入到向量库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法（追加导入）
  python -m backend.app.agent.vector.pgvector_init.import_data data.json

  # 覆盖导入（清空现有数据后重新导入）
  python -m backend.app.agent.vector.pgvector_init.import_data data.json --overwrite

  # 指定集合名称和批量大小
  python -m backend.app.agent.vector.pgvector_init.import_data data.json --collection-name my_collection --batch-size 50

  # 指定内容字段和元数据字段
  python -m backend.app.agent.vector.pgvector_init.import_data data.json --content-field text --metadata-fields type domain

环境变量要求:
  DATABASE_URL     - PostgreSQL 数据库连接字符串（格式: postgresql+psycopg://user:password@host:port/database）
  NVIDIA_API_KEY   - NVIDIA API Key 用于生成向量嵌入

注意:
  使用 --overwrite 选项会清空集合中所有现有数据，请谨慎使用。
        """
    )

    parser.add_argument(
        "json_file",
        type=str,
        help="要导入的 JSON 文件路径",
    )

    parser.add_argument(
        "--collection-name",
        type=str,
        default="rag_store",
        help="向量集合名称（默认: rag_store）",
    )

    parser.add_argument(
        "--pg-connection-string",
        type=str,
        default=None,
        help="PostgreSQL 连接字符串（默认: 使用 DATABASE_URL 环境变量）",
    )

    parser.add_argument(
        "--nvidia-api-key",
        type=str,
        default=None,
        help="NVIDIA API Key（默认: 使用 NVIDIA_API_KEY 环境变量）",
    )

    parser.add_argument(
        "--embedding-model",
        type=str,
        default="baai/bge-m3",
        help="Embedding 模型名称（默认: baai/bge-m3）",
    )

    parser.add_argument(
        "--content-field",
        type=str,
        default="document",
        help="指定 JSON 数组中用于文档内容的字段名（默认: document）",
    )

    parser.add_argument(
        "--metadata-fields",
        type=str,
        nargs="*",
        default=None,
        help="指定用作元数据的字段列表（默认: 使用除 document 字段外的所有字段）",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批量导入大小（默认: 100）",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖模式：清空表中所有现有数据后再导入",
    )

    parser.add_argument(
        "--encoding",
        type=str,
        default="utf-8",
        help="JSON 文件编码（默认: utf-8）",
    )

    args = parser.parse_args()

    try:
        # 加载 JSON 数据
        logger.info(f"正在加载 JSON 文件: {args.json_file}")
        data = load_json_data(
            json_file_path=args.json_file,
            encoding=args.encoding,
        )

        if not data:
            logger.warning("JSON 文件为空，无需导入")
            return 0

        # 确定导入模式
        if args.overwrite:
            logger.warning("⚠️  覆盖模式已启用，将清空集合中所有现有数据！")
            # 简单确认提示
            response = input(f"确认要清空集合 '{args.collection_name}' 中的所有数据吗？(yes/no): ")
            if response.lower() not in ["yes", "y"]:
                logger.info("导入已取消")
                return 0

        # 导入数据到向量库
        imported_count = import_data_to_vector_store(
            data=data,
            table_name=args.collection_name,
            pg_connection_string=args.pg_connection_string,
            nvidia_api_key=args.nvidia_api_key,
            embedding_model=args.embedding_model,
            content_field=args.content_field,
            metadata_fields=args.metadata_fields,
            batch_size=args.batch_size,
            clear_existing=args.overwrite,
            progress_callback=progress_callback,
        )

        print()  # 换行
        logger.info(f"✓ 导入完成！共导入 {imported_count} 个文档")
        return 0

    except FileNotFoundError as e:
        logger.error(f"文件不存在: {e}")
        return 1
    except ValueError as e:
        logger.error(f"数据格式错误: {e}")
        return 1
    except Exception as e:
        logger.error(f"导入失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
