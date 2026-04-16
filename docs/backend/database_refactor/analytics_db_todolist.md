# Analytics DB 后续待办清单

修改时间：2026-04-11 Asia/Shanghai

主要修改内容：
- 新增 `analytics_db` 数据库重构待办清单，按“已完成 / 建议下一步 / 可选增强”分层整理
- 明确当前是否可以只依赖 `mart_vehicle_quality_360` 让 LLM 自主生成 SQL
- 给出“什么时候需要新增主题 mart，什么时候可以继续复用现有 mart”的判断依据

## 1. 目的

这份清单用于后续继续扩展 `analytics_db` 时快速决策：

- 哪些数据库设计已经完成
- 哪些适合下一步优先做
- 哪些属于后续可选增强
- 哪些问题现在已经可以只靠现有 `mart` 回答

## 2. 当前已完成

截至 2026-04-11，当前数据库主链路已经完成：

- `analytics_db` 分析库已建立
- `src_rb / src_defect / ods / dim / fct / mart / meta` 分层已建立
- `fct.fct_position_current_all`
- `fct.fct_vehicle_position_current`
- `fct.fct_abnormal_vehicle_current`
- `fct.fct_vehicle_defect_detection`
- `mart.mart_vehicle_quality_360`
- `mart.mart_abnormal_vehicle_current`
- `mart.mart_position_current_overview`
- `dim.dim_process_area`
- `dim.dim_vehicle_profile`
- `meta.refresh_analytics_all()`
- `agent_ro` 对新增对象的只读权限

当前已经能稳定支持：

- 正式产品车当前分布
- 异常车当前分布
- 当前现场总览
- 缺陷汇总分析
- 产品车缺陷与当前位置的关联分析

## 3. 建议下一步

这些属于“值得继续做，但不是现在不用就会坏”的项。

### 3.1 缺陷趋势主题 `mart`

建议新增：

- `mart_defect_daily_by_model`

作用：

- 面向“按天 / 车型 / 黑车顶 / tunnel / cycle”的缺陷趋势问题
- 降低 LLM 自己写时间聚合 SQL 的复杂度
- 让高频日报、周报类问题更稳定

典型问题：

- 最近 7 天各车型缺陷趋势
- 某车型这周缺陷是否升高
- 黑车顶车型每日缺陷趋势

### 3.2 缺陷部位分布主题 `mart`

建议新增：

- `mart_defect_station_distribution`

作用：

- 面向 5 个部位缺陷分布问题
- 让模型不必每次自己展开 `station_1_defect_count ~ station_5_defect_count`
- 让“哪个部位是主要缺陷来源”这类问题更稳

典型问题：

- 某车型哪些部位缺陷最多
- 不同 `tunnel` 下哪个部位缺陷最高
- 某时间段缺陷主要集中在右侧还是车顶

### 3.3 Agent 接库切换

建议后续尽快完成：

- 在 `.env` 中补齐 `ANALYTICS_DATABASE_URL`
- 把后端 SQL Agent 默认切到 `analytics_db`

原因：

- 现在数据库准备好了，但应用层还没完全接过去
- 不切过去，数据库重构的收益还没有完全释放

## 4. 可选增强

这些属于“后面业务需要了再做”。

### 4.1 位置历史快照层

适用场景：

- 要分析停留时长
- 要分析路径
- 要分析时序关系

当前是否必需：

- 暂时不是

### 4.2 检测时位置关联主题表

适用场景：

- 缺陷检测发生位置并不固定
- 或你要严格还原“检测当时位置”

当前是否必需：

- 你目前已经说明每台车都在同一个位置检测
- 所以现阶段可以不做

### 4.3 接入缺陷明细层

例如：

- `history`
- `history_detail`
- `history_station`

适用场景：

- 要分析缺陷类型
- 要分析坐标、区域、明细归因

当前是否必需：

- 对汇总分析不是必需
- 对高级质量分析会有价值

## 5. 现在只靠 `mart_vehicle_quality_360`，LLM 自主生成 SQL 可以吗

可以，而且对你们当前一大类问题来说，**准确率可以做到比较高**。

原因是：

- 它已经把缺陷汇总和产品车当前位置收敛到一张表
- 对 LLM 来说，单表聚合通常比多表 `JOIN` 更稳定
- 车型、黑车顶、颜色、`tunnel`、`cycle`、5 个部位缺陷数都已经在表内

所以像这些问题，当前直接用 `mart_vehicle_quality_360` 一般是可行的：

- 某时间范围各车型缺陷总量
- 各车型每日缺陷趋势
- 某车型不同 `tunnel` / `cycle` 的缺陷差异
- 黑车顶和非黑车顶缺陷对比
- 5 个部位缺陷分布
- 异常高缺陷检测记录

## 6. 既然 LLM 能直接写，为什么还要继续加主题 mart

因为“能查出来”和“长期稳定、便宜、统一口径”不是一回事。

### 6.1 只靠 `mart_vehicle_quality_360` 的优点

- 开发快
- 少建表
- 适合中低频探索式问题
- 当前已经够支撑很多分析

### 6.2 只靠 `mart_vehicle_quality_360` 的不足

- 每次都让 LLM 自己写时间聚合和部位展开，稳定性会波动
- 高重复问题会反复生成类似 SQL，成本更高
- 口径容易随着提问方式变化而轻微漂移
- 如果后续做报表或固定场景，主题 mart 会更稳

## 7. 什么时候应该新增主题 mart

满足下面任一条件，就值得新增：

- 某类问题问得很频繁
- 同类 SQL 反复出现
- 结果口径必须高度一致
- 需要更快响应
- 需要给固定技能场景直接绑定稳定对象

## 8. 当前建议的决策

如果你现在要控制投入，我建议这样选：

### 方案 A：先不继续建新 mart

适合：

- 当前主要还是探索式问答
- 问题量不大
- 想先把 Agent 接到 `analytics_db`

建议动作：

- 直接先用 `mart_vehicle_quality_360`
- 异常车问题用 `mart_abnormal_vehicle_current`
- 当前现场分布用 `mart_position_current_overview`

### 方案 B：再补 2 张主题 mart

适合：

- 缺陷趋势和部位分布是高频问题
- 想让 LLM 更稳、更快
- 后面要沉淀固定技能场景

建议动作：

- 新增 `mart_defect_daily_by_model`
- 新增 `mart_defect_station_distribution`

## 9. 推荐执行顺序

1. 先完成 Agent 接入 `ANALYTICS_DATABASE_URL`
2. 观察真实问答中最常见的问题
3. 如果趋势类问题高频，新增 `mart_defect_daily_by_model`
4. 如果部位分布问题高频，新增 `mart_defect_station_distribution`
5. 如果后面出现时序分析需求，再做位置历史快照层

## 10. 一句话结论

当前数据库第一阶段已经够用，`mart_vehicle_quality_360` 也足够支撑很多 LLM 自主 SQL 问题；后续是否继续加主题 `mart`，主要看你是更偏“灵活探索”，还是更偏“高频稳定分析”。
