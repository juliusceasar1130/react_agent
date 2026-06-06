# 120JPH 涂装车间 AI 智能助手（汇报版）

本方案专为**非技术管理层与业务人员**设计，采用“卡片式概念图”阐述设计思路，不体现复杂的数据库连接与技术细节，重点体现**业务场景的分类治理、核心支撑以及业务价值**。

---

## 一、 整体设计概念图 (Bento Cards)

```mermaid
graph TB
    %% 样式定义 - 汇报专用高级配色
    classDef titleStyle fill:#1971c2,stroke:#1864ab,stroke-width:2px,color:#ffffff,font-size:20px,font-weight:bold;
    classDef brainStyle fill:#fff9db,stroke:#f59f00,stroke-width:2px,color:#704300,font-size:14px;
    classDef flowStyle fill:#f8f9fa,stroke:#ced4da,stroke-width:2px,color:#495057,font-size:14px;
    classDef skillStyle fill:#f3f0ff,stroke:#845ef7,stroke-width:2px,color:#3b1175,font-size:14px;
    classDef baseStyle fill:#ebfbee,stroke:#40c057,stroke-width:2px,color:#094f1c,font-size:14px;

    %% 核心概念标题
    Title["💡 120JPH 涂装 AI 智能助手<br/>『 业务人员的一站式数据分析大脑 』"]:::titleStyle

    %% 三个平级并列的核心支柱
    subgraph PILLAR_A["RAG 业务知识库"]
        direction LR
        A1["业务方言辞典<br/>『自动翻译车间黑话与缩写』"]:::brainStyle
        A2["优化 DDL 资产<br/>『提供精确的表结构注释与关联关系』"]:::brainStyle
    end

    subgraph PILLAR_B["智能路由与场景分流"]
        direction LR
        B1["随机与长尾问题<br/>『大模型自主根据宽表进行推理』"]:::flowStyle
        B2["高频简单查询<br/>『SQL RAG Few-shot 直接检索套用』"]:::flowStyle
        B3["复杂高频分析<br/>『加载专用业务 Skill 技能处理』"]:::flowStyle
    end

    subgraph PILLAR_C["Skill 领域技能和场景开发"]
        direction LR
        C1["固定输出格式与规范<br/>『确保工业指标、报表输出100%严谨一致』"]:::skillStyle
        C2["复杂多步推理与专家组件<br/>『定制相邻车缺陷分析、滞留车分析等高阶逻辑』"]:::skillStyle
        C3["扩展工具集调用<br/>『支持绘图、外部接口等高级业务扩展功能』"]:::skillStyle
    end

    %% 位于底部的数据底座（数据基石支撑）
    subgraph PILLAR_BASE["统一分析数据底座"]
        direction LR
        Base1["多源数据库连接<br/>『打破实时车辆、缺陷检测、过点历史等物理库壁垒』"]:::baseStyle
        Base2["数据清洗与重构<br/>『过滤物理库脏数据，重构为面向 LLM 优化的极简主题宽表』"]:::baseStyle
    end

    %% 布局排版控制 (并列排列，由底座统一支撑)
    Title ~~~ PILLAR_B
    PILLAR_A ~~~ PILLAR_BASE
    PILLAR_B ~~~ PILLAR_BASE
    PILLAR_C ~~~ PILLAR_BASE
```

---

## 二、 业务场景治理亮点

对非技术决策者而言，本方案的核心成效在于**“分流治理，各尽所能”**：

| 业务场景 | 我们的处理逻辑 | 业务汇报价值亮点 |
| :--- | :--- | :--- |
| **随机与长尾提问** | **大模型自主根据宽表进行推理** | 💡 **无死角的灵活性**：对于临时性、非固化的提问，直接利用大模型的强大泛化能力，基于预先净化的主题宽表进行自主推理，给业务人员留有充分的自由度。 |
| **高频简单查询** | **SQL RAG Few-shot 直接检索套用** | ⚡ **极速与零偏差**：将高频简单的指标查询通过相似度检索，直接套用预设的 SQL 范例，避开复杂推理过程，**响应极快且逻辑绝对正确**。 |
| **复杂高频分析** | **Skill 领域技能和场景开发** | 🎯 **专家级精准度**：针对极具深度的业务指标（如相邻车缺陷分析、滞留车分析），通过开发固定的 Skill 技能，锁死计算口径与图表格式，保证**输出质量绝对稳定可靠**。 |
