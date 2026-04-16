## 1. Implementation

- [x] 1.1 为技能系统新增 `business-skills` spec delta，明确场景聚合目录和自动发现要求
- [x] 1.2 重构技能发现/注册逻辑，使领域和场景基于目录约定自动装配
- [x] 1.3 调整资产引用与解析方式，支持 `scope + path` 语义
- [x] 1.4 迁移 `paint_shop_vehicle_tracking` 现有场景到 `scenarios/<scenario_name>/` 结构
- [x] 1.5 更新渲染器、加载器与运行时调用链，确保对外接口保持不变
- [x] 1.6 更新技能专题文档、README 与 changelog，统一到新范式

## 2. Verification

- [x] 2.1 验证自动发现后 `get_skill_by_name()`、`list_scenarios_by_skill()`、`get_scenario_by_name()` 结果正确
- [x] 2.2 验证 `load_domain_content()` 与 `load_scenario_content()` 仍能输出完整文本
- [x] 2.3 验证场景资产和 shared 资产都能按 scope 正确解析
- [x] 2.4 验证无须修改 `registry.py` 即可接入新增场景
- [x] 2.5 验证错误场景目录、重复场景名和无效资产路径会触发明确报错
