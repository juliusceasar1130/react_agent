## Context

`export_to_csv` 已经能在服务器侧落盘 CSV，但其输出仍是“服务器绝对路径 + 文本说明”，这既不安全，也无法被浏览器直接消费。

## Goals / Non-Goals

- Goals:
  - 让前端基于聊天消息直接下载 CSV
  - 不暴露服务器绝对路径
  - 尽量少改现有 SSE 和消息存储结构
- Non-Goals:
  - 不引入数据库级导出记录表
  - 不引入对象存储或多机共享存储
  - 不重构现有聊天消息协议

## Decisions

- Decision: 使用 sidecar JSON 元数据文件保存导出记录
  - Why: 最小改动，不依赖数据库迁移，服务重启后短期仍可下载
- Decision: `export_to_csv` 返回 JSON 字符串
  - Why: 保持现有 `tool_results: Dict[str, str]` 契约不变
- Decision: 前端在 `MessageItem.vue` 中按工具名 `export_to_csv` 识别下载卡片
  - Why: 能同时兼容流式与非流式消息落库结构

## Risks / Trade-offs

- 单机临时目录方案不适合多实例部署
- 下载失败时目前主要依赖后端 HTTP 状态返回，前端未额外封装复杂错误处理

## Migration Plan

1. 新增导出文件元数据服务与配置项
2. 新增后端下载接口
3. 调整导出工具返回值
4. 新增前端下载卡片
5. 更新文档与变更记录
