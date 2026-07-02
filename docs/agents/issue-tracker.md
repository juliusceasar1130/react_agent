# Issue tracker: Local Markdown

Issues and PRDs for this repo live as markdown files in `.scratch/`.

## 配置信息

- **格式**: 带有 YAML Frontmatter 的 Markdown 文件。
- **存放路径**: `.scratch/<feature-slug>/<NN>-<slug>.md`
- **PRD**: `.scratch/<feature-slug>/PRD.md`
- **分拣状态**: 在每个 issue 文件的开头通过 `Status:` 行记录（参见 `triage-labels.md` 中的标签字符串）

## 工作流

1. **创建**: `to-issues` 或 `to-prd` 等技能在 `.scratch/<feature-slug>/` 下创建新的 Markdown 文件。
2. **更新**: 修改文件内容或 Frontmatter 以反映进度。
3. **评论**: 在 `## Comments` 标题下追加会话历史。
4. **关闭**: 将文件移至 `closed/` 子目录，或更新 `Status:` 字段。
