# backend/app/agent/utils/test_skeleton_service.py
from backend.app.agent.utils.skeleton_service import SkeletonService

class DummyDB:
    def __init__(self):
        self._custom_table_info = {
            "fct_vehicle_position_current": "CREATE TABLE fct_vehicle_position_current (\n  vehicle_id VARCHAR\n);\n-- 1. {'vehicle_id': '123'}\n-- 2. {'vehicle_id': '456'}"
        }

def test_get_skeleton_ddl():
    db = DummyDB()
    service = SkeletonService(db)
    
    # 验证物流追踪技能
    ddl = service.get_skeleton_ddl("paint_shop_vehicle_logistics")
    
    assert "CREATE TABLE fct_vehicle_position_current" in ddl
    assert "vehicle_id VARCHAR" in ddl
    # 🔴 核心断言：验证尾部的样本数据已经被成功剔除
    assert "-- 1." not in ddl
    assert "-- 2." not in ddl
