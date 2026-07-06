# backend/app/agent/utils/skeleton_service.py
"""
辅助技能骨架 DDL 服务。

修改时间: 2026-07-05 Asia/Shanghai
主要修改内容:
- 新增 table_primary_keys 读取：在 DDL 骨架中标注主键列
- 新增 relationships 读取：在骨架末尾渲染紧凑型跨域关联路径声明
  （格式：`[`基数`安全标记`] from_key -> to_key + note 说明 + 💡 预聚合模板）
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
        获取辅助技能的骨架 DDL（含主键标注 + 聚焦关系图）。

        Returns:
            完整的骨架文本，包含 DDL 骨架块和跨域关系声明块。
            若技能无关联表则返回空字符串。
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

        # ── 1. 生成 DDL 骨架块（含主键标注） ──
        table_primary_keys = meta.get("table_primary_keys", {})
        skeleton_blocks = self._build_ddl_blocks(
            associated_tables, table_info, table_primary_keys
        )

        # ── 2. 生成跨域关系声明块 ──
        relationships = meta.get("relationships", [])
        relationship_block = self._build_relationship_block(
            skill_name, relationships
        )

        # ── 3. 拼装最终输出 ──
        parts = []
        if skeleton_blocks:
            parts.append("\n\n".join(skeleton_blocks))
            logger.info(
                f"✅ 技能 {skill_name} DDL 骨架拼装完成，"
                f"共加载 {len(skeleton_blocks)} 个辅助表结构"
            )
        if relationship_block:
            parts.append(relationship_block)

        return "\n\n".join(parts) if parts else ""

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
        table_primary_keys: dict,
    ) -> list[str]:
        """为每张辅助表生成清理后的 DDL 骨架，并标注主键列。"""
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

            # 🔑 标注主键列：在主键列定义末尾追加 " PRIMARY KEY" 注释
            pk_col = table_primary_keys.get(full_table_name)
            if pk_col:
                # 在主键列名后追加 "  -- PK" 标记
                # 匹配列定义行（以 "  col_name" 开头的行）
                pk_pattern = rf"(^\s+{re.escape(pk_col)}\s+\S+.*$)"
                replacement = rf"\1  -- PK"
                clean_ddl, count = re.subn(
                    pk_pattern, replacement, clean_ddl, flags=re.MULTILINE
                )
                if count > 0:
                    logger.info(
                        f"🔑 辅助表 {table_name} 主键列已标注: {pk_col}"
                    )
                else:
                    # 列名可能不在缓存 DDL 中（如视图），降级为头部注释
                    header_comment = (
                        f"-- Primary Key: {pk_col}\n"
                    )
                    clean_ddl = header_comment + clean_ddl
                    logger.info(
                        f"🔑 辅助表 {table_name} 主键列 {pk_col} 通过头部注释标注"
                    )

            skeleton_blocks.append(clean_ddl)
            logger.info(f"💡 成功加载辅助表 DDL 骨架: {table_name}")

        return skeleton_blocks

    # ──────────────────────────────────────────────────────────────
    # 内部方法：跨域关系声明块
    # ──────────────────────────────────────────────────────────────

    def _build_relationship_block(
        self, skill_name: str, relationships: list[dict]
    ) -> str:
        """
        将 relationships 列表渲染为紧凑型跨域关系声明文本。

        输出格式示例：
            ## 跨域关联路径 (Join Keys & Cardinality)
            - [`1:N`⚠️] fct.fct_vehicle_position_current.vehicle_id -> mart.mart_vehicle_quality_360.vehicle_id
              > 位置表一车一行，质量360一车多行；JOIN 前必须预聚合
              💡 SELECT vehicle_id, COUNT(*) AS cnt FROM ... GROUP BY vehicle_id
            - [`N:1`✅] fct.fct_vehicle_position_current.process_area -> dim.dim_process_area.process_area
              > 维度表唯一，安全 JOIN
        """
        if not relationships:
            return ""

        lines = [
            "## 跨域关联路径 (Join Keys & Cardinality)",
            "",
        ]

        for rel in relationships:
            from_table = rel.get("from_table", "未知表")
            from_key = rel.get("from_key", "?")
            to_table = rel.get("to_table", "未知表")
            to_key = rel.get("to_key", "?")
            cardinality = rel.get("cardinality", "?")
            join_safety = rel.get("join_safety", "unknown")
            note = rel.get("note", "")
            pre_agg = rel.get("pre_aggregate_hint", "")

            # 基数前缀 + 安全标记
            if join_safety == "safe":
                prefix = f"[`{cardinality}`✅]"
            elif join_safety == "unsafe":
                prefix = f"[`{cardinality}`⚠️]"
            else:
                prefix = f"[`{cardinality}`❓]"

            # 主行：[基数] from_table.from_key -> to_table.to_key
            lines.append(
                f"- {prefix} {from_table}.{from_key} -> {to_table}.{to_key}"
            )

            # note 作为缩进说明
            if note:
                lines.append(f"  > {note}")

            # 预聚合模板（仅 unsafe 且有 hint）
            if pre_agg and join_safety == "unsafe":
                lines.append(f"  💡 {pre_agg}")

            lines.append("")

        logger.info(
            f"📊 技能 {skill_name} 渲染了 {len(relationships)} 条跨域关联路径"
        )
        return "\n".join(lines)
