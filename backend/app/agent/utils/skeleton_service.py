# backend/app/agent/utils/skeleton_service.py
import re
import logging

logger = logging.getLogger(__name__)

class SkeletonService:
    def __init__(self, db):
        """
        💡 零开销复用：直接传入系统初始化好的 db 实例，读取已常驻内存的表定义缓存
        """
        self.db = db

    def get_skeleton_ddl(self, skill_name: str) -> str:
        # 1. 动态加载目标技能的 meta.py 获取关联表名
        try:
            meta_module = __import__(f"backend.app.skills.domains.{skill_name}.meta", fromlist=["DOMAIN_META"])
            associated_tables = getattr(meta_module, "DOMAIN_META", {}).get("associated_tables", [])
        except Exception as err:
            logger.error(f"加载技能 {skill_name} 的元数据失败: {err}")
            return ""

        if not associated_tables:
            logger.info(f"技能 {skill_name} 没有定义关联辅助表 associated_tables")
            return ""

        table_info = getattr(self.db, "_custom_table_info", None)
        if not table_info:
            logger.warning("数据库对象中不存在 _custom_table_info 缓存字典")
            return ""

        # 2. 直接从 db 缓存中提取 DDL 并使用正则剥离样本行以防 Token 膨胀
        skeleton_blocks = []
        for full_table_name in associated_tables:
            table_name = full_table_name.split('.')[-1] if '.' in full_table_name else full_table_name
            if table_name in table_info:
                ddl = table_info[table_name]
                # 🔴 正则剥离尾部的样本数据行 (-- 1. {'vehicle_id': ...})
                clean_ddl = re.sub(r'-- \d+\. \{.*?\}', '', ddl, flags=re.DOTALL).strip()
                # 💡 正则裁减：将 VARCHAR(50) / VARCHAR(255) 等类型长度修饰符统一还原为极简 VARCHAR
                clean_ddl = re.sub(r'VARCHAR\(\d+\)', 'VARCHAR', clean_ddl, flags=re.IGNORECASE)
                skeleton_blocks.append(clean_ddl)
                logger.info(f"💡 成功加载辅助表 DDL 骨架: {table_name}")
            else:
                logger.warning(f"⚠️ 内存缓存 _custom_table_info 中未找到辅助表: {table_name}")

        final_skeleton = "\n\n".join(skeleton_blocks)
        if final_skeleton:
            logger.info(f"✅ 技能 {skill_name} 拼装完成，共加载 {len(skeleton_blocks)} 个辅助表结构")
        return final_skeleton
