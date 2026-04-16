# 缺陷检测汇总表 Schema

## 数据表

### history_station_defect_summary（缺陷检测汇总表）

- 描述：Eines检测日志，包含5个站点/部位的缺陷数量统计、总缺陷数量。
- 关键字段：
  - `history_id` (INTEGER)：检测编号，对应原始检测记录的唯一标识
  - `model` (INTEGER)：车型编码，原始业务中的车型代号，数字编码
  - `type_name` (VARCHAR(100))：车型名称， `A7`、`TiguanL`、`Tiguan Pro`
  - `black_roof` (VARCHAR(100))：黑车顶标记，代表该记录只包含车顶检测
  - `serial_number` (VARCHAR(255))：fis号码、车身ID
  - `date_time` (TIMESTAMP)：检测时间
  - `color_code` (VARCHAR(255))：颜色代码
  - `tunnel` (INTEGER)：检测通道,1、2、3代表1线、2线、3线检测
  - `cycle` (INTEGER)： 同一个fis号码，检测次数
  - `station_1_defect_count` (INTEGER)：右侧缺陷数量
  - `station_2_defect_count` (INTEGER)：左侧缺陷数量
  - `station_3_defect_count` (INTEGER)：车顶缺陷数量
  - `station_4_defect_count` (INTEGER)：前盖缺陷数量
  - `station_5_defect_count` (INTEGER)：尾门缺陷数量
  - `total_defect_count` (INTEGER)：总缺陷数量，等于右侧、左侧、车顶、前盖、尾门缺陷数量之和

## 业务逻辑

### 汇总口径

- 一条 `history_station_defect_summary` 记录对应一次检测
- 缺陷统计范围限定为 `station 1~5`
- `station_1_defect_count` 到 `station_5_defect_count` 依次表示右侧、左侧、车顶、前盖、尾门的缺陷数量
- `total_defect_count` 是全部部位的总缺陷数量

## 分析建议

### 适合大模型回答的问题

- 某时间范围内各车型的缺陷总量和工位分布
- 某车型在不同 `tunnel`、`cycle` 下的缺陷差异
- 黑车顶车型与非黑车顶车型的缺陷数量对比
- 单次检测是否存在异常高缺陷数
- 哪些工位是主要缺陷来源

### 使用注意事项

- `type_name` 是由 `model` 映射得到的可读车型名称，不是原始业务编码
- `black_roof` 是文本标记字段，不是严格布尔值
- 若某个 `model` 没有映射，`type_name` 和 `black_roof` 可能为空
- 该表是汇总结果，不包含单条缺陷的位置、类型、坐标等明细信息
