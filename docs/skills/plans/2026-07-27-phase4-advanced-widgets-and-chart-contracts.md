# Phase 4: 高级控件与 UI/数据契约扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成直通查询参数解析器中 `date` / `daterange` 日期控件类型的推断支持，扩展 `formatter.py` 的 `chart` 图表契约数据格式化输出，并在前端补全日期选择器与图表渲染支持。

**Architecture:** 在 `resolver.py` 的 `infer_widget` 中扩展日期与时间范围推断分支；在 `formatter.py` 中扩展 `output_type=="chart"` 的折线图/柱状图序列化逻辑；在前端注册 `DateWidget.vue` 并映射 `date` 与 `daterange` 组件。

**Tech Stack:** Python 3.12, FastAPI, Vue 3, Element Plus / Naive UI / Tailwind CSS Date Picker.

---

### User Review Required

> [!IMPORTANT]
> **向下兼容与图表结构**：图表输出契约 (`output_type=="chart"`) 默认采用首列作为横坐标 (`categories`)、后续列作为多指标序列 (`series`) 的通用结构，同时保留 `rows` 和 `columns` 字段，前端可无缝回退展示表格形态。

---

### Proposed Changes & File Mapping

#### Backend Direct-Path Engine

##### [MODIFY] [resolver.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/resolver.py)
- 在 `infer_widget` 中添加 `date`, `datetime`, `daterange` 的推断逻辑。

##### [MODIFY] [formatter.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/formatter.py)
- 在 `format_result` 函数中加入 `output_type=="chart"` 的转换分支，输出 `categories` 与 `series` 结构。

#### Frontend Components

##### [NEW] [DateWidget.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/widgets/DateWidget.vue)
- 创建 Vue 3 日期 / 日期范围选择器控件组件。

##### [MODIFY] [ParameterForm.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ParameterForm.vue)
- 注册 `DateWidget.vue` 并扩充 `getWidgetComponent` 中的 `"date"` 与 `"daterange"` 映射。

---

## Detailed Task Breakdown

### Task 1: 后端控件推断增强 - `resolver.py` 支持 `date` 与 `daterange`

**Files:**
- Modify: `backend/app/skills/direct_path/resolver.py:19-32`

- [ ] **Step 1: 定位 `infer_widget` 推断分支**

打开 `backend/app/skills/direct_path/resolver.py` 找到第 19 行：
```python
def infer_widget(param_type: str, has_source_table: bool, explicit_widget: str | None = None) -> str:
    if explicit_widget:
        return explicit_widget
    
    param_type_lower = (param_type or "").lower()
    if param_type_lower == "string":
        return "select" if has_source_table else "text"
    elif param_type_lower in ("integer", "number", "float"):
        return "number"
    elif param_type_lower == "array":
        return "multiselect"
    return "text"
```

- [ ] **Step 2: 扩充日期类型推断分支**

在 `resolver.py` 中更新 `infer_widget`：
```python
def infer_widget(param_type: str, has_source_table: bool, explicit_widget: str | None = None) -> str:
    """推断前端 Widget 类型。"""
    if explicit_widget:
        return explicit_widget
    
    param_type_lower = (param_type or "").lower()
    if param_type_lower in ("date", "datetime"):
        return "date"
    elif param_type_lower in ("daterange", "date_range"):
        return "daterange"
    elif param_type_lower == "string":
        return "select" if has_source_table else "text"
    elif param_type_lower in ("integer", "number", "float"):
        return "number"
    elif param_type_lower == "array":
        return "multiselect"
    return "text"
```

- [ ] **Step 3: 验证推断逻辑**

运行 Python 测试：
```bash
python -c "from backend.app.skills.direct_path.resolver import infer_widget; assert infer_widget('date', False) == 'date'; assert infer_widget('daterange', False) == 'daterange'; print('Widget infer test passed!')"
```
Expected output: `Widget infer test passed!`

---

### Task 2: 图表输出格式化扩展 - `formatter.py` 支持 `chart`

**Files:**
- Modify: `backend/app/skills/direct_path/formatter.py`

- [ ] **Step 1: 检查 `formatter.py` 中的 `format_result`**

查看 `backend/app/skills/direct_path/formatter.py`：
```python
def format_result(rows: list[tuple], columns: list[str], output_type: str = "table") -> dict[str, Any]:
    if output_type == "scalar":
        ...
    formatted_rows = [list(row) for row in rows]
    return {
        "type": "table",
        "columns": columns,
        "rows": formatted_rows,
        "row_count": len(formatted_rows),
    }
```

- [ ] **Step 2: 扩展 `chart` 输出格式转化逻辑**

更新 `backend/app/skills/direct_path/formatter.py` 为：
```python
"""
结果格式化层 (Formatter)

职责：将原始数据库查询行转化为前端渲染组件（Table / Scalar / Chart）直接可用的 JSON 数据形态。
"""

from typing import Any


def format_result(rows: list[tuple], columns: list[str], output_type: str = "table") -> dict[str, Any]:
    """根据 output_type 将数据库查询行格式化为输出数据。"""
    if output_type == "scalar":
        val = rows[0][0] if rows and len(rows[0]) > 0 else 0
        return {
            "type": "scalar",
            "value": val,
            "label": "查询结果",
        }
    
    if output_type == "chart":
        formatted_rows = [list(row) for row in rows]
        categories = [str(row[0]) for row in rows] if rows else []
        
        y_cols = columns[1:] if len(columns) > 1 else (columns if columns else ["数值"])
        series_data = []
        for idx, col_name in enumerate(y_cols, start=1 if len(columns) > 1 else 0):
            series_data.append({
                "name": col_name,
                "data": [row[idx] if idx < len(row) else None for row in rows] if rows else [],
            })
            
        return {
            "type": "chart",
            "columns": columns,
            "categories": categories,
            "series": series_data,
            "rows": formatted_rows,
            "row_count": len(formatted_rows),
        }
    
    # 默认 "table"
    formatted_rows = [list(row) for row in rows]
    return {
        "type": "table",
        "columns": columns,
        "rows": formatted_rows,
        "row_count": len(formatted_rows),
    }
```

- [ ] **Step 3: 验证图表格式化结果**

运行 Python 验证测试：
```bash
python -c "from backend.app.skills.direct_path.formatter import format_result; res = format_result([('2026-05-12', 45), ('2026-05-13', 60)], ['date', 'count'], 'chart'); print(res); assert res['type'] == 'chart' and len(res['categories']) == 2"
```
Expected output: 成功输出包含 `categories` 与 `series` 结构字典，断言通过。

---

### Task 3: 前端 DateWidget 组件创建与注册

**Files:**
- Create: `frontend/src/components/widgets/DateWidget.vue`
- Modify: `frontend/src/components/ParameterForm.vue`

- [ ] **Step 1: 创建 `frontend/src/components/widgets/DateWidget.vue`**

新建 `frontend/src/components/widgets/DateWidget.vue` 文件：
```vue
<template>
  <div class="date-widget">
    <input
      :type="isRange ? 'text' : 'date'"
      :value="modelValue"
      :placeholder="placeholder || (isRange ? 'YYYY-MM-DD 至 YYYY-MM-DD' : '选择日期')"
      class="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue?: string
  placeholder?: string
  isRange?: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()
</script>
```

- [ ] **Step 2: 检查并定位 `ParameterForm.vue` 控件映射**

搜索 `frontend/src/components/ParameterForm.vue` 中的控件组件引入与 getter：
```typescript
import TextWidget from './widgets/TextWidget.vue'
import SelectWidget from './widgets/SelectWidget.vue'
```

- [ ] **Step 3: 注册 `DateWidget.vue` 并添加 `date` / `daterange` 分支**

在 `ParameterForm.vue` 中引入并映射：
```typescript
import DateWidget from './widgets/DateWidget.vue'

const getWidgetComponent = (widgetType: string) => {
  switch (widgetType) {
    case 'select':
      return SelectWidget
    case 'date':
    case 'daterange':
      return DateWidget
    default:
      return TextWidget
  }
}
```

---

## Verification Plan

### Automated Verification
1. 后端单元校验：
   ```bash
   conda run -n py312_agent python -c "from backend.app.skills.direct_path.resolver import infer_widget; from backend.app.skills.direct_path.formatter import format_result; assert infer_widget('date', False) == 'date'; res = format_result([(10, 20)], ['a', 'b'], 'chart'); assert res['type'] == 'chart'; print('Backend Phase 4 verified successfully!')"
   ```

### Manual Verification
1. 启动前端 `npm run dev`，配置包含 `type: "date"` 的参数并在直通弹窗中选择日期；
2. 校验日期字符串提交后构建出的 SQL 条件与返回结果。
