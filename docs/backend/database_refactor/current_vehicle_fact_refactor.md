# 当前车辆事实分层重构方案

修改时间：2026-04-11 Asia/Shanghai

主要修改内容：
- 新增围绕“正式产品车 / 异常车 / 全量占位”重构当前车辆事实层的设计方案
- 说明当前 `fct_vehicle_position_current` 在异常车和重复调试 `vehicle_id` 场景下的局限
- 提出新的 `fct` / `mart` 分层建议，为后续 Agent 查询与分析库演进提供实施依据
- 补充 2026-04-11 已实际落地到 `analytics_db` 的第一阶段对象与验证结果
- 明确哪些步骤已经完成，哪些仍属于下一阶段优化

## 0. 当前已落地状态

截至 2026-04-11，以下对象已经在 `analytics_db` 中实际落地并刷新成功：

- `fct.fct_position_current_all`
- `fct.fct_vehicle_position_current`
- `fct.fct_abnormal_vehicle_current`
- `mart.mart_abnormal_vehicle_current`
- `mart.mart_position_current_overview`

同时，`dim.dim_vehicle_profile` 已补充当前绑定快照字段：

- `current_position_id`
- `current_carrier_id`
- `current_carrier_type`
- `current_process_area`
- `current_full_rb_code`
- `current_position_updated_at`

当次校验结果：

- `fct.fct_position_current_all`：`114`
- `fct.fct_vehicle_position_current`：`102`
- `fct.fct_abnormal_vehicle_current`：`12`
- `mart.mart_abnormal_vehicle_current`：`12`
- `mart.mart_position_current_overview`：`114`

异常车分类样例：

- `empty_vehicle_id_with_carrier`：`8`
- `non_product_prefix`：`4`

## 1. 背景

当前 `analytics_db` 已经具备：

- `ods.rb_position_data`
- `fct.fct_position_current_all`
- `fct.fct_vehicle_position_current`
- `fct.fct_abnormal_vehicle_current`
- `fct.fct_vehicle_defect_detection`
- `mart.mart_abnormal_vehicle_current`
- `mart.mart_vehicle_quality_360`

本次重构的起点，是旧版 `fct.fct_vehicle_position_current` 曾经采用如下定义方式：

- 从 `ods.rb_position_data` 中
- 按 `vehicle_id`
- 用 `DISTINCT ON (vehicle_id)` 取最新一条记录

这套逻辑在“正式产品车”场景里基本成立，但在“异常车 / 调试车”场景里存在天然限制。

## 2. 当前问题

### 2.1 重复调试 `vehicle_id` 会被错误压缩

如果车间内有多台临时调试车使用同一个 `vehicle_id`，例如：

- `88888888888888`

并且它们分布在不同位置，那么当前逻辑最终只会保留其中一条最新记录。

这意味着：

- 当前 `fct.fct_vehicle_position_current` 不能代表“全部当前占位”
- 它只能代表“按 `vehicle_id` 唯一化之后的当前记录”

### 2.2 异常车和产品车的建模依据不同

正式产品车通常满足：

- `vehicle_id` 以前缀 `782026` 开头
- 可将 `vehicle_id` 视为比较稳定的唯一业务标识

异常车则不一样。根据现有项目知识文档，异常车辆有两类：

1. `vehicle_id` 的前缀不是 `782026` 开头，且 `carrier_id != 0`
2. `vehicle_id = '--------------'`，且 `carrier_id != 0`

在这两类场景下：

- `vehicle_id` 可能不是正式业务 ID
- `vehicle_id` 可能重复
- `vehicle_id` 甚至可能是占位值

因此不能继续把“产品车事实”和“异常车事实”混在同一个按 `vehicle_id` 去重的事实表中。

### 2.3 旧版 `mart_vehicle_quality_360` 会继承这个偏差

因为当前 `mart.mart_vehicle_quality_360` 依赖：

- `fct.fct_vehicle_defect_detection`
- `fct.fct_vehicle_position_current`

因此在重构前，只要底层 `fct.fct_vehicle_position_current` 对异常车口径不完整，`mart` 也会继承这个偏差。

## 3. 重构目标

本轮重构的目标不是推翻现有分析库，而是把当前车辆事实层做得更稳、更清晰：

1. 保留当前已经可用的产品车分析能力
2. 明确区分正式产品车与异常车
3. 保留“当前全部占位”的完整表达能力
4. 为 Agent 提供更清晰的数据入口，避免口径混淆

## 4. 当前事实层设计

当前已将“当前车辆位置事实”拆成三层，其中前两层和异常车主题 `mart` 已经落地。

### 4.1 `fct_position_current_all`

当前语义：

- 当前每个有效占位一条记录
- 面向“现场当前全貌”

当前粒度：

- 一条占位记录一行

当前唯一依据：

- 优先使用位置实体或采集点实体，而不是 `vehicle_id`

当前实现：

- 使用 `position_id`
- 同时保留 `full_rb_code = plc + rb_index`
- 不按 `vehicle_id` 去重

适用问题：

- 当前总共有多少占位
- 某区域当前有哪些占位
- 当前有哪些载体在使用
- 当前产品车、异常车、空位分别占多少

### 4.2 `fct_vehicle_position_current`

当前语义：

- 当前正式产品车事实

当前口径：

- 已明确收窄到正式产品车
- 当前过滤：
  - `vehicle_id LIKE '782026%'`
  - `body_type <> '-----'`
  - `carrier_id <> '0'`

唯一依据：

- `vehicle_id`

适用问题：

- 现在每个区域有多少正式产品车
- 某产品车当前在哪
- 某车型当前分布

### 4.3 `fct_abnormal_vehicle_current`

当前语义：

- 当前异常车事实

当前口径：

- 已从 `fct_position_current_all` 中筛出异常车
- 不按 `vehicle_id` 唯一去重

当前关键字段：

- `abnormal_type`
- `abnormal_reason`

当前已落地分类：

- `non_product_prefix`
- `empty_vehicle_id_with_carrier`

适用问题：

- 当前异常车有多少
- 异常车分布在哪些区域
- 哪些载体上是异常车

## 5. 对 `mart` 的影响

### 5.1 保留现有 `mart_vehicle_quality_360`

建议保留，但语义要更明确：

- 它应被视为“正式产品车质量分析主表”
- 不再隐含承担“全部当前占位”的职责

### 5.2 新增异常车主题 `mart`

当前已新增：

- `mart_abnormal_vehicle_current`

用途：

- 面向异常车监控与查询
- 给 Agent 回答异常车相关问题

### 5.3 视需要增加全量现场总览 `mart`

当前已落地：

- `mart_position_current_overview`

用途：

- 面向当前总览问题
- 同时容纳产品车、异常车、空位与特殊占位

## 6. 为什么不直接继续沿用当前 `fct_vehicle_position_current`

因为当前这张表背后有一个隐含假设：

- `vehicle_id` 能稳定标识唯一车身

而这个假设并不适用于异常车或调试车。

如果继续沿用当前模式，会带来这些问题：

1. 多台调试车共用同一 `vehicle_id` 时，会被错误合并
2. 异常车统计会系统性低估
3. `carrier_id -> vehicle_id` 的当前绑定关系不完整
4. Agent 会误把“产品车事实”当成“全部车辆事实”

## 7. 推荐查询入口

为了让 Agent 后续更稳定，建议查询入口按主题区分：

- 正式产品车当前分布：
  - `fct_vehicle_position_current`
- 当前异常车监控：
  - `fct_abnormal_vehicle_current`
  - 或 `mart_abnormal_vehicle_current`
- 当前现场总览：
  - `fct_position_current_all`
  - 或 `mart_position_current_overview`
- 质量与当前位置关联：
  - `mart_vehicle_quality_360`

## 8. 实施顺序建议

### 阶段 1：保留现状，补充文档认知

状态：已完成

先明确：

- 当前 `fct_vehicle_position_current` 更适合产品车
- 当前 `mart_vehicle_quality_360` 更适合产品车质量分析

### 阶段 2：新增全量当前占位事实

状态：已完成

新增：

- `fct_position_current_all`

先把现场当前占位能力完整保住。

### 阶段 3：拆出异常车事实

状态：已完成

新增：

- `fct_abnormal_vehicle_current`

明确异常车分类与查询入口。

### 阶段 4：收窄产品车事实定义

状态：已完成

将当前：

- `fct_vehicle_position_current`

明确收敛为正式产品车当前事实。

### 阶段 5：扩展 `mart`

状态：已完成第一阶段

已完成：

- `mart_abnormal_vehicle_current`
- `mart_position_current_overview`

后续可继续增加：

- 更细粒度的时序或停留时长主题 `mart`

## 9. 当前建议

当前第一阶段已经完成。下一步如果继续优化，我建议优先做：

1. 视需要增加异常车分类细分
2. 规划位置历史快照层
3. 再考虑“检测时位置”而不是“当前位置”的质量关联
4. 按业务主题继续拆更细的总览或监控 `mart`

这样做的好处是：

- 不会推翻当前已经可用的分析链路
- 全量现场当前状态、正式产品车、异常车已经有独立入口
- 后续可以围绕时序和总览主题继续扩展

## 10. 一句话总结

当前车辆事实层最大的优化方向，不是把一张表越做越万能，而是把“全部占位、正式产品车、异常车”三类口径明确拆开，各自服务自己的分析问题。
