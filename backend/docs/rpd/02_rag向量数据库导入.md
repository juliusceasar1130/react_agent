# rag向量数据库数据导入
## 背景：
    -现有的agent D:\Python\workplace\rearch_agent\.tree\features\agent\backend\app\agent智能体使用来了skill加载的功能，让llm先判断领域知识范畴再加载预定义的数据表格schema信息
    - 受到.tree\features\agent\docs\rpd\07_SQL_RAG_开发最佳实践.md和.tree\features\agent\docs\rpd\08_Agent_核心机制深度解析.md 思路启发，需要开发基于rag的业务知识预检索和填充功能
## 目前需求：
    - agent检索功能基本完成
    - 需要开发向量数据库的增删改查功能，以便后续检索使用
    - 为简化开发过程，使用数据导入功能，实现数据更新
       - 数据采用json格式
    - 使用脚本文件对数据进行导入，相关代码和文件放置在D:\Python\workplace\rearch_agent\.tree\features\agent\backend\plan\vector
    - 需要考虑初始化，没有集合的情况，需要创建集合
    - 以json文件为数据源，导入后覆盖集合数据
    - 参考 02_rag向量数据库导入.md
