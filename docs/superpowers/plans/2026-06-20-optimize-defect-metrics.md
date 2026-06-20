# Optimize Defect Metrics LLM Target Indicators (Count and Mean) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the SQL Agent queries average defect count and detection count as default metrics in the quality defect domain rather than the total sum of defects, by enhancing system prompt rules and injecting RAG few-shot SQL examples.

**Architecture:** 
1. Modify `domain.md` of the `paint_shop_defect_analysis` domain to inject strict `[!IMPORTANT]` rules prioritizing `COUNT(*)` (frequency) and `AVG(total_defect_count)` (mean) while discouraging `SUM(total_defect_count)`.
2. Append defect-specific few-shot SQL examples demonstrating these metrics to both Milvus and PGVector initialization JSON datasets.
3. Execute the Milvus database index reload script to rebuild the hybrid vector search database.

**Tech Stack:** LangChain, Milvus, Python 3.12, PostgreSQL

---

### Task 1: Update Domain Knowledge Prompts

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_defect_analysis/domain.md`

- [ ] **Step 1: Edit the guidelines in domain.md**

  Locate lines 86-90 in [domain.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/skills/domains/paint_shop_defect_analysis/domain.md):
  ```markdown
  ### 指标

  - 相比缺陷总数/总量，**次数**和**均值**更有价值。如果用户没有明确指定，优先使用**次数**和**均值**作为统计指标
  - **单车** 不是唯一车，通常指均值，计算公式=**检测总数/检测次数**。禁止使用唯一车身进行统计，除非用户指定
  ```

  Replace it with:
  ```markdown
  ### 指标

  > [!IMPORTANT]
  > **质量缺陷统计核心军规（大模型编写 SQL 时必须无条件严格遵守）：**
  > 1. **默认统计口径**：除非用户在提问中显式要求统计“缺陷总数”、“缺陷总量”或“累计缺陷数”（例如明确提出“求总和/SUM”），否则所有缺陷分析、趋势图表 and 统计默认**必须且只能**计算以下两个核心指标：
  >    - **检测次数 (detection_count)**: `COUNT(*)`，即检测的频次或记录条数。
  >    - **平均单次检测缺陷数 (avg_defect_per_detection)**: `AVG(total_defect_count)`，即缺陷均值。
  > 2. **严禁越界行为**：严禁默认生成仅包含 `SUM(total_defect_count)` 聚合的 SQL 查询。如果用户提问含糊（例如“展示缺陷趋势”或“对比不同通道的缺陷”），必须同时计算并返回 `COUNT(*)` 以及 `AVG(total_defect_count)`。
  > 3. **“单车”业务概念澄清**：在此领域中，“单车缺陷”或“单车缺陷水平”通常指的是“平均每次检测的缺陷数（`AVG`）”。计算公式 = 检测缺陷总数 / 检测次数。严禁使用唯一车身（`COUNT(DISTINCT serial_number)`）来进行平均值计算，除非用户指明。
  ```

- [ ] **Step 2: Commit the changes**
  Run:
  ```bash
  git add backend/app/skills/domains/paint_shop_defect_analysis/domain.md
  git commit -m "feat: strengthen defect analysis metric guidelines to prioritize average and count"
  ```

---

### Task 2: Inject Few-Shot SQL Examples for RAG

**Files:**
- Modify: `backend/app/agent/vector/milvus_init/data/examples/example_sql_example.json`
- Modify: `backend/app/agent/vector/pgvector_init/examples/example_sql_example.json`

- [ ] **Step 1: Append defect SQL examples in milvus_init/data/examples/example_sql_example.json**

  Insert the following three JSON items into the array in [example_sql_example.json](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/milvus_init/data/examples/example_sql_example.json):

  ```json
  [
    ... (existing items) ...,
    {
      "document": "问题：查询某车型缺陷趋势、每日缺陷变化 SQL：SELECT DATE(mq.detect_time) AS stat_date, mq.defect_type_name, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY DATE(mq.detect_time), mq.defect_type_name ORDER BY stat_date DESC;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT DATE(mq.detect_time) AS stat_date, mq.defect_type_name, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY DATE(mq.detect_time), mq.defect_type_name ORDER BY stat_date DESC;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "按日期和车系统计检测次数与单车平均缺陷数（推荐口径）"
      }
    },
    {
      "document": "问题：对比不同检测通道的缺陷差异、通道缺陷对比 SQL：SELECT mq.tunnel, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.tunnel ORDER BY mq.tunnel;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT mq.tunnel, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.tunnel ORDER BY mq.tunnel;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "对比不同检测通道（tunnel）下的检测次数与单车平均缺陷数"
      }
    },
    {
      "document": "问题：分析不同检测次数下的车型缺陷、不同cycle缺陷对比 SQL：SELECT mq.defect_type_name, mq.cycle, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.defect_type_name, mq.cycle ORDER BY mq.defect_type_name, mq.cycle;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT mq.defect_type_name, mq.cycle, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.defect_type_name, mq.cycle ORDER BY mq.defect_type_name, mq.cycle;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "按车系和检测次数（cycle）分组统计检测次数与单车平均缺陷数"
      }
    }
  ]
  ```

- [ ] **Step 2: Append defect SQL examples in pgvector_init/examples/example_sql_example.json**

  Insert the same three items into the array in [example_sql_example.json](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/agent/vector/pgvector_init/examples/example_sql_example.json):

  ```json
  [
    ... (existing items) ...,
    {
      "document": "问题：查询某车型缺陷趋势、每日缺陷变化 SQL：SELECT DATE(mq.detect_time) AS stat_date, mq.defect_type_name, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY DATE(mq.detect_time), mq.defect_type_name ORDER BY stat_date DESC;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT DATE(mq.detect_time) AS stat_date, mq.defect_type_name, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY DATE(mq.detect_time), mq.defect_type_name ORDER BY stat_date DESC;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "按日期 and 车系统计检测次数与单车平均缺陷数"
      }
    },
    {
      "document": "问题：对比不同检测通道的缺陷差异、通道缺陷对比 SQL：SELECT mq.tunnel, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.tunnel ORDER BY mq.tunnel;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT mq.tunnel, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.tunnel ORDER BY mq.tunnel;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "对比不同检测通道（tunnel）下的检测次数与单车平均缺陷数"
      }
    },
    {
      "document": "问题：分析不同检测次数下的车型缺陷、不同cycle缺陷对比 SQL：SELECT mq.defect_type_name, mq.cycle, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.defect_type_name, mq.cycle ORDER BY mq.defect_type_name, mq.cycle;",
      "metadata": {
        "type": "sql_example",
        "sql": "SELECT mq.defect_type_name, mq.cycle, COUNT(*) AS detection_count, AVG(mq.total_defect_count) AS avg_defect_per_detection FROM mart_vehicle_quality_360 mq GROUP BY mq.defect_type_name, mq.cycle ORDER BY mq.defect_type_name, mq.cycle;",
        "complexity": "medium",
        "domain": "paint_shop_defect_analysis",
        "description": "按车系 and 检测次数（cycle）分组统计检测次数与单车平均缺陷数"
      }
    }
  ]
  ```

- [ ] **Step 3: Commit the changes**
  Run:
  ```bash
  git add backend/app/agent/vector/milvus_init/data/examples/example_sql_example.json backend/app/agent/vector/pgvector_init/examples/example_sql_example.json
  git commit -m "feat: add few-shot SQL examples for defect average and count statistics"
  ```

---

### Task 3: Rebuild Vector Search Store

**Files:**
- Run scripts to reload vector collections.

- [ ] **Step 1: Re-initialize Milvus Index**
  Run:
  ```powershell
  conda activate py312_agent
  python -m backend.app.agent.vector.milvus_init.init_milvus
  ```
  Expected Output: Success, showing that the document count has increased and the RAG collection was re-initialized.

---
