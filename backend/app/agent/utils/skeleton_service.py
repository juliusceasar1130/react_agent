# backend/app/agent/utils/skeleton_service.py
"""
辅助技能骨架 DDL 服务。

修改时间: 2026-07-05 Asia/Shanghai
主要修改内容:
- 简化骨架生成：仅返回清理后的 DDL 块，PK 信息由 db_utils.py 自动反射注入 DDL
- 移除 table_primary_keys 和 relationships 的手动标注逻辑
"""

import re
import logging

logger = logging.getLogger(__name__)


class SkeletonService:
    def __init__(self, db):
        """
        💡 零开销复用：直接传入系统初始化好的 db 实例，读取已常驻内存的表定义缓存
        """
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────────────────────

    def get_skeleton_ddl(self, skill_name: str) -> str:
        """
        获取辅助技能的骨架 DDL。

        Returns:
            DDL 骨架文本。若技能无关联表则返回空字符串。
        """
        meta = self._load_meta(skill_name)
        if meta is None:
            return ""

        associated_tables = meta.get("associated_tables", [])
        if not associated_tables:
            logger.info(f"技能 {skill_name} 没有定义关联辅助表 associated_tables")
            return ""

        table_info = getattr(self.db, "_custom_table_info", None)
        if not table_info:
            logger.warning("数据库对象中不存在 _custom_table_info 缓存字典")
            return ""

        skeleton_blocks = self._build_ddl_blocks(associated_tables, table_info)
        if not skeleton_blocks:
            return ""

        logger.info(
            f"✅ 技能 {skill_name} DDL 骨架拼装完成，"
            f"共加载 {len(skeleton_blocks)} 个辅助表结构"
        )
        return "\n\n".join(skeleton_blocks)

    # ──────────────────────────────────────────────────────────────
    # 内部方法：加载元数据
    # ──────────────────────────────────────────────────────────────

    def _load_meta(self, skill_name: str) -> dict | None:
        """动态加载目标技能的 DOMAIN_META 字典。"""
        try:
            meta_module = __import__(
                f"backend.app.skills.domains.{skill_name}.meta",
                fromlist=["DOMAIN_META"],
            )
            return getattr(meta_module, "DOMAIN_META", None)
        except Exception as err:
            logger.error(f"加载技能 {skill_name} 的元数据失败: {err}")
            return None

    # ──────────────────────────────────────────────────────────────
    # 内部方法：DDL 骨架块（含主键标注）
    # ──────────────────────────────────────────────────────────────

    def _build_ddl_blocks(
        self,
        associated_tables: list[str],
        table_info: dict,
    ) -> list[str]:
        """为每张辅助表生成清理后的 DDL 骨架。"""
        skeleton_blocks: list[str] = []

        for full_table_name in associated_tables:
            table_name = (
                full_table_name.split(".")[-1]
                if "." in full_table_name
                else full_table_name
            )

            if table_name not in table_info:
                logger.warning(
                    f"⚠️ 内存缓存 _custom_table_info 中未找到辅助表: {table_name}"
                )
                continue

            ddl = table_info[table_name]
            # 🔴 正则剥离尾部的样本数据行 (-- 1. {'vehicle_id': ...})
            clean_ddl = re.sub(r"-- \d+\. \{.*?\}", "", ddl, flags=re.DOTALL).strip()
            # 💡 正则裁减：将 VARCHAR(50) / VARCHAR(255) 等类型长度修饰符统一还原为极简 VARCHAR
            clean_ddl = re.sub(
                r"VARCHAR\(\d+\)", "VARCHAR", clean_ddl, flags=re.IGNORECASE
            )

            skeleton_blocks.append(clean_ddl)
            logger.info(f"💡 成功加载辅助表 DDL 骨架: {table_name}")

        return skeleton_blocks

    # ──────────────────────────────────────────────────────────────
    # 内部方法：跨域关系声明块（已移除，PK 军规则由 service.py 统一管控）
    # ──────────────────────────────────────────────────────────────
