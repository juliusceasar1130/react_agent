# 04 — 全量构建打包、单元测试验证与重构路线图收敛

**What to build:**
执行 `git grep` 验证 0 残留引用，执行 `npm run build` 验证 0 错误打包，运行后端 `pytest` 确保全绿，更新 `refactoring_roadmap.md`、`changelog.md` 与交付总结。

**Blocked by:**
- 01 — 改造前端组件调用点为直通领域路径并恢复深度思考等组件渲染
- 02 — 物理清理前端根目录 20 个已废弃的 .vue 兼容 Shim 垫片
- 03 — 后端主入口直连 routers 模块并清理后端已废弃 Shim 文件

**Status:** completed

- [x] 运行 `git grep -n "@/components/[A-Z]" frontend/src` 确保 0 残留
- [x] 运行前端编译检查 `npm run build` 确保 0 报错 (793 modules transformed, built in 14.31s)
- [x] 运行后端单元测试 `python -m pytest backend/tests` 确保全绿 (35 passed, 4 deselected in 16.66s)
- [x] 运行后端启动验证 `python -c "from backend.app.main import app"` 确保 100% 成功启动
- [x] 更新 `refactoring_roadmap.md`、`changelog.md` 与 `README.md`
