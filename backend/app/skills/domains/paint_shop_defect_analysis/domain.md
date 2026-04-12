# 涂装车间质量缺陷分析架构

修改时间：2026-04-12 Asia/Shanghai

主要修改内容：
- 新增质量缺陷分析领域文档
- 基于 `analytics_db` 说明缺陷汇总分析的推荐查询入口
- 明确车型趋势、部位分布、tunnel/cycle 对比、黑车顶对比等常见问题的查询口径

## 数据来源

当前质量缺陷分析主要基于：

- 源汇总表：`history_station_defect_summary`
- 分析库主对象：`mart_vehicle_quality_360`

其中：

- `serial_number = vehicle_id`
- 一条 `history_station_defect_summary` 记录代表一次检测
- 当前分析重点是汇总层，不包含缺陷坐标、类型和明细位置

## 推荐查询入口

当 Agent 默认连接 `analytics_db` 时，质量缺陷问题优先使用以下对象：

### 优先级

1. 优先查询 `mart`
2. 其次查询 `fct`
3. 非必要不直接查询 `ods`

### 核心分析对象

#### `mart_vehicle_quality_360`

- 当前质量缺陷分析主表
- 适用问题：
  - 某时间范围各车型缺陷总量
  - 某车型不同 `tunnel` / `cycle` 的缺陷差异
  - 黑车顶和非黑车顶缺陷对比
  - 5 个部位缺陷分布
  - 单次检测的异常高缺陷识别

主要字段：

- `history_id`
- `vehicle_id`
- `detect_time`
- `defect_model`
- `defect_type_name`
- `defect_black_roof`
- `defect_color_code`
- `tunnel`
- `cycle`
- `station_1_defect_count`
- `station_2_defect_count`
- `station_3_defect_count`
- `station_4_defect_count`
- `station_5_defect_count`
- `total_defect_count`
- `process_area`
- `carrier_id`
- `carrier_type`

#### `fct_vehicle_defect_detection`

- 缺陷检测事实层
- 一条记录代表一次检测
- 适合更底层的检测事实查询

## 业务口径

### 一次检测一条记录

- `history_id` 唯一标识一次检测
- 同一台车可以有多次检测，通过 `cycle` 区分

### 5 个部位含义

- `station_1_defect_count`：右侧
- `station_2_defect_count`：左侧
- `station_3_defect_count`：车顶
- `station_4_defect_count`：前盖
- `station_5_defect_count`：尾门

### 总缺陷数量

- `total_defect_count` 是 5 个部位缺陷数量之和

### tunnel / cycle

- `tunnel` 表示检测通道
- `cycle` 表示同一车身的检测次数
- 分析 tunnel 或 cycle 差异时，应该明确是否按检测次数统计，还是按唯一车身统计

## 常见问题类型

### 车型趋势

- 某时间范围内各车型缺陷总量
- 某车型每日缺陷趋势
- 某车型近期缺陷是否升高

### 部位分布

- 哪些部位是主要缺陷来源
- 某车型缺陷集中在哪些部位
- 不同 `tunnel` 下哪个部位缺陷更多

### 对比分析

- 黑车顶 vs 非黑车顶
- 不同 `tunnel` 对比
- 不同 `cycle` 对比

### 异常识别

- 哪些检测记录缺陷数异常高
- 哪些车型在某时间窗口缺陷波动明显

## 当前易错点

### `type_name` 与 `model` 不是一回事

- `defect_model` / `model` 是业务编码
- `defect_type_name` / `type_name` 是可读车型名称

### `black_roof` 不是严格布尔值

- 它是文本标记字段
- 查询时需要结合业务语义判断，不应简单假设所有非空值都一致

### 当前质量关联口径是“缺陷检测 + 当前最新位置”

- `mart_vehicle_quality_360` 当前关联的是当前最新位置
- 不是检测当时位置
- 如果后续需要时序位置分析，应增加位置历史快照层

### 当前不包含缺陷明细

- 现阶段主要面向汇总分析
- 如果后续要分析缺陷类型、坐标、明细区域，需要再接入 `history_detail` 等明细表

## 推荐回答策略

- 趋势问题：优先按 `DATE(detect_time)` 聚合
- 车型问题：优先使用 `defect_type_name`，必要时补充 `defect_model`
- 部位问题：明确 5 个 `station_*_defect_count` 的业务含义
- 对比问题：说明是否按检测次数统计，还是按唯一车身统计
