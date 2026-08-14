# 02 — 物理清理前端根目录 20 个已废弃的 .vue 兼容 Shim 垫片

**What to build:**
物理删除 `frontend/src/components/` 根目录下的 20 个过渡 Shim 文件，保持前端组件根目录干净清爽。

**Blocked by:** 01 — 改造前端组件调用点为直通领域路径并恢复深度思考等组件渲染.

**Status:** completed

- [x] 删除 `frontend/src/components/` 下的 20 个 `.vue` 垫片文件
- [x] 确保子目录 `chat/`, `agent/`, `artifacts/`, `common/`, `widgets/`, `chat/plugins/` 完整保留
