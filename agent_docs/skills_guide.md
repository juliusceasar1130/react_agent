# Skills 开发约定

> 从 memory.md 迁出，在开发或修改 Skills 时读取。
> 详细指南参考 `docs/skills/guide.md`。

## 约定

- **元数据驱动**：所有领域 (`meta.py`) 和场景 (`scenario.py`) 必须定义 `title` 和 `example_questions`。
- **目录发现**：场景技能通过 `backend/app/skills/domains/<domain>/scenarios/` 目录结构自动发现并加载，无需手动注册到中心化列表。
- **视觉标准**：前端仪表盘采用 **Arctic Glass** 风格。所有图标容器应适配 `bg-gradient-to-br` 与 `shadow-glow`。
- **SQL 工具调用**：通过 `required_skill` 显式声明依赖领域。
- **加载顺序**：先加载领域技能（domain skill），必要时再加载场景技能（scenario skill）。
