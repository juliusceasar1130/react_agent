# 新增业务领域技能 (Domain Skill) 开发指南

> **文档版本**: v1.1  
> **归档位置**: `docs/skills/domain_skill_development_guide.md`  
> **面向对象**: 后端 Agent 开发者、算法工程师

---

## 1. 业务领域 (Domain) 架构与能力定位

在技能系统中，**业务领域技能 (Domain Skill)** 是同一业务场景集合的顶层组织单元（如 `paint_shop_vehicle_logistics` 涂装车身物流、`paint_shop_defect_analysis` 涂装质量缺陷）。

领域技能负责：
1. 向 LLM 系统的 System Prompt 提供高层级的 **领域知识摘要**（包含表结构、通用业务规则）；
2. 组织与管理其下辖的所有 **场景技能 (Scenario Skill)** 与 **共享资产 (`shared/`)**。

---

## 2. 目标目录结构

创建一个新领域技能时，必须在 `backend/app/skills/domains/` 下建立对应的领域目录：

```text
backend/app/skills/domains/
└── [domain_name]/                     # 领域目录（例如: paint_shop_vehicle_logistics）
    ├── meta.py                        # 领域元数据配置文件 (必填)
    ├── domain.md                      # 领域公共上下文描述文件 (必填)
    ├── shared/                        # [可选] 跨场景共享资产
    │   ├── sql/                       # 共享 SQL 片段
    │   └── scripts/                   # 共享脚本
    └── scenarios/                     # [必填] 下辖业务场景目录
        └── [scenario_name]/           # 各具体场景 (包含 scenario.py 与 sql/main.sql)
```

---

## 3. 标准开发步骤

### 第 1 步：创建领域目录

在 `backend/app/skills/domains/` 下创建英文目录（如 `paint_shop_defect_analysis`）。

### 第 2 步：编写 `meta.py`

在领域目录下新建 `meta.py`，必须定义 `DOMAIN_META` 字典：

```python
# backend/app/skills/domains/paint_shop_defect_analysis/meta.py

DOMAIN_META = {
    "name": "paint_shop_defect_analysis",       # [必填] 领域唯一 key，必须与目录名 100% 一致
    "title": "质量缺陷分析",                    # [必填] 首页展示及 API 识别的中文标题
    "description": "涂装车间质量缺陷汇总分析、车型缺陷趋势、通道/周期对比与漏检监控。", # [必填] 领域一句话业务摘要
    "tags": ["paint_shop", "quality", "defect", "scenario_enabled"], # [必填] 业务标签
}
```

**代码级约束 (`discovery.py`)**：
- `DOMAIN_META["name"]` 必须为非空字符串；
- `meta.py` 中的 `name` 必须与所在目录名 **100% 完全匹配**，否则自动发现抛出 `ValueError`。

### 第 3 步：编写 `domain.md`

在领域目录下新建 `domain.md`，书写供 LLM 阅读的全局业务上下文与常用维度表结构（如 `dim_process_area` / `mart_position_current_overview`）。

### 第 4 步：按需创建 `shared/` 共享资产

若该领域下有多个场景需要复用 SQL 规则或说明脚本，可存放在 `shared/` 目录下，在场景元数据中通过 `"scope": "shared"` 进行引用。

---

## 4. 自动发现与校验 (`discovery.py`)

系统通过 `backend/app/skills/discovery.py` 的 `discover_domains()` 自动扫描：
1. 自动读取 `meta.py` 中的 `DOMAIN_META`；
2. 强校验同目录下必须存在 `domain.md`；
3. 校验目录名一致性与重名重复；
4. 装配至全局注册表 `DOMAIN_SKILLS`。

重启后端服务或调用 `reload_skills()` 即可自动生效，**无需手动在 `registry.py` 中注册**。
