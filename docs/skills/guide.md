# AI 助手技能开发指南 (Skills Development Guide)

本指南旨在规范 AI 助手的“领域技能 (Domain Skill)”与“场景技能 (Scenario Skill)”的编写，确保首页 Dashboard 动态渲染与后台大模型逻辑的一致性。

---

## 1. 目录结构规范

所有技能必须存放在 `backend/app/skills/domains/` 目录下，遵循以下层级：

```text
domains/
└── [domain_name]/              # 领域目录（如 paint_shop_defect_analysis）
    ├── meta.py                 # 领域元数据（用于首页展示与注册）
    ├── domain.md               # 领域上下文描述（用于大模型 Prompt）
    └── scenarios/              # 场景子目录
        └── [scenario_name]/    # 场景目录（如 daily_defect_summary）
            ├── scenario.py     # 场景元数据（用于首页展示、意图识别与参数提取）
            └── sql/            # 场景配套 SQL 资产
                └── main.sql    # SQL 模板文件
```

---

## 2. 领域元数据编写 (`meta.py`)

`meta.py` 必须包含 `DOMAIN_META` 字典，用于首页卡片渲染。

### 规范与示例
```python
# backend/app/skills/domains/[domain_name]/meta.py

DOMAIN_META = {
    "name": "paint_shop_defect_analysis",      # [必填] 内部唯一 ID，必须与目录名一致
    "title": "质量缺陷分析",                   # [必填] 首页 Dashboard 显示的标题
    "description": "涂装车间质量缺陷汇总分析...", # [必填] 首页 Dashboard 显示的描述
    "tags": ["paint_shop", "quality", "defect", "scenario_enabled"], # [必填] 标签，必须包含 scenario_enabled
}
```

---

## 3. 场景元数据编写 (`scenario.py`)

`scenario.py` 必须包含 `SCENARIO` 字典，是首页“引导问题”与大模型“执行逻辑”的核心。

### 规范与示例
```python
# backend/app/skills/domains/[domain_name]/scenarios/[scenario_name]/scenario.py

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis", # [必填] 所属领域名称，必须准确
    "name": "daily_defect_summary",             # [必填] 内部唯一 ID，必须与目录名一致
    "title": "每日缺陷汇总",                    # [必填] 首页显示的二级标题
    "description": "统计每日缺陷总量与分布...", # [必填] 场景功能详细描述
    
    "example_questions": [                      # [必填] 首页展示的示例问题（建议 2-3 个）
        "今天缺陷情况怎么样？",
        "查看昨天的缺陷汇总",
        "统计最近三天的车型缺陷分布"
    ],
    
    "triggers": [                               # [必填] 大模型意图匹配的触发词
        "今天缺陷情况怎么样",
        "按天汇总缺陷"
    ],
    
    "intent_keywords": ["每日", "汇总"],         # [必填] 辅助识别关键词
    
    "required_inputs": [],                      # [必填] 必填参数名列表（无参数填空数组）
    "optional_inputs": ["date_range"],          # [必填] 可选参数名列表（无参数填空数组）
    
    "parameters": {                             # [可选] 参数定义，仅在有参数时必填
        "date_range": {
            "type": "string",                   # [必填] 参数类型
            "description": "查询的时间范围",    # [必填] 参数描述
            "required": False,                  # [必填] 是否必填
            "source_column": "detect_time",     # [可选] 对应数据库列名
            "source_table": "xxx",              # [可选] 对应数据库表名
            "example_values": ["2026-05-12"],   # [必填] 示例值
            "usage": "说明如何使用该参数",      # [必填] 使用说明
            "sql_fragment": "AND..."            # [必填] SQL 片段模板
        }
    },
    
    "workflow": [ "步骤1...", "步骤2..." ],      # [必填] LLM 执行步骤指导
    "rules": [ "规则1..." ],                    # [必填] 强制执行规则
    "gotchas": [ "注意点1..." ],                # [必填] 常见坑点提示
    
    "output_contract": "输出字段说明...",         # [必填] 结果字段约定
    
    "sql_template_refs": [                      # [必填] 绑定的 SQL 资产（无 SQL 填空数组）
        {
            "type": "sql",                      # [必填] 资产类型
            "name": "main",                     # [必填] 资产名称
            "scope": "scenario",                # [必填] 作用域 (scenario/domain)
            "path": "sql/main.sql",             # [必填] 相对路径
            "description": "主查询模板"         # [必填] 资产描述
        }
    ]
}
```

---

## 4. 关键规则 (Checklist)

在提交新技能前，请务必核对：

- [ ] **目录名一致性**：领域目录名必须等于 `DOMAIN_META["name"]`，场景目录名必须等于 `SCENARIO["name"]`。
- [ ] **关联关系**：场景中的 `skill_name` 必须指向正确的领域 `name`。
- [ ] **首页文案**：`title`（中文标题）和 `example_questions`（用户引导）是否已填写？
- [ ] **SQL 路径**：`sql_template_refs` 中的 `path` 是否相对于场景目录下的 `sql/` 文件夹？
- [ ] **无死代码**：确保每个 `scenarios/[name]/` 目录下都有 `__init__.py`（可以为空），以便 Python 包发现。

---

## 5. 自动发现机制说明

系统通过 `backend/app/skills/discovery.py` 自动扫描 `domains` 目录。
- **首页更新**：只要 `meta.py` 和 `scenario.py` 配置正确，重启后端服务后，前端 Dashboard 会自动渲染新技能。
- **大模型生效**：注册后的技能会自动合并到大模型的 System Prompt 中，使其具备处理相关业务问题的能力。
