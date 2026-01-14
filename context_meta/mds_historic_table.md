# MDS Historic 数据库表结构

> **创建时间**: 2026-01-11
> **数据库**: MySQL (localhost/mds)
> **表名**: mds_historic

## 表结构

| 字段名 | 类型 | 说明 | 别名/同义词 | 备注 |
|--------|------|------|-------------|------|
| ID | varchar(255) | 主键ID | GUID, UUID | |
| DATE_EVT | varchar(255) | 事件日期 | EVENT_DATE, OCCURRED_AT | |
| SHIFT_NR | varchar(255) | 班次编号 | SHIFT_NO, SHIFT_NUMBER | |
| RW_STATION_ID | varchar(255) | 读写站ID | READ_WRITE_STATION, RFID_STATION | |
| RW_STATION_STATUS | varchar(255) | 读写站状态 | STATION_STATUS, READER_STATUS | |
| SKID_ID | varchar(255) | 滑橇ID | PALLET_ID, TRAY_ID, CARRIER_ID | |
| SKID_TYPE | varchar(255) | 滑橇类型 | PALLET_TYPE, CARRIER_TYPE | |
| SKID_IS_EMPTY | varchar(255) | 滑橇是否为空 | PALLET_EMPTY, IS_PALLET_EMPTY | |
| BODY_ID | varchar(255) | 车身ID | CAR_BODY_ID, VEHICLE_ID, CAR_ID | |
| BODY_TYPE | varchar(255) | 车身类型 | CAR_BODY_TYPE, VEHICLE_TYPE | |
| MDS_DATA | varchar(255) | MDS数据 | TELEGRAM_DATA, MDS_PAYLOAD | |
| MDS_TELEGRAM_TYPE | varchar(255) | MDS电报类型 | TELEGRAM_TYPE, MESSAGE_TYPE | |
| FK_ERP_HIST_ID | varchar(255) | ERP历史外键 | ERP_HISTORY_ID, ERP_REF_ID | |
| CYCLE_NUM | varchar(255) | 周期数 | CYCLE_NUMBER, SEQUENCE_NUM | |
| PRODUCTION_SEGMENT_ID | varchar(255) | 生产工段ID | SEGMENT_ID, WORK_SEGMENT_ID | |
| ETL_MODIFY_DATE | varchar(255) | ETL修改日期 | ETL_UPDATED_AT, LOAD_DATE | |
| ETL_SOURCE_ID | varchar(255) | ETL数据源ID | SOURCE_SYSTEM, DATA_SOURCE | |

## 字段补充说明（请填写别名）

请在上面的"别名/同义词"和"备注"列中补充字段的其他称呼：

| 字段名 | 别名/同义词（逗号分隔） | 备注 |
|--------|------------------------|------|
| ID | | |
| DATE_EVT | | |
| SHIFT_NR | | |
| RW_STATION_ID | | |
| RW_STATION_STATUS | | |
| SKID_ID | | |
| SKID_TYPE | | |
| SKID_IS_EMPTY | | |
| BODY_ID | | |
| BODY_TYPE | | |
| MDS_DATA | | |
| MDS_TELEGRAM_TYPE | | |
| FK_ERP_HIST_ID | | |
| CYCLE_NUM | | |
| PRODUCTION_SEGMENT_ID | | |
| ETL_MODIFY_DATE | | |
| ETL_SOURCE_ID | | |

## 备注

- 共 17 个字段
- 所有字段类型均为 varchar(255)
- 该表目前没有字段注释
- 建议添加字段注释以提升大模型理解能力
