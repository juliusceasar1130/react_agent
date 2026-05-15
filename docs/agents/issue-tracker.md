# Issue Tracker: Local Markdown

本项目使用本地 Markdown 文件进行问题追踪。

## 配置信息

- **格式**: 带有 YAML Frontmatter 的 Markdown 文件。
- **存放路径**: `.scratch/<feature>/<issue-id>.md`
- **分拣流程**: `triage` 技能会读取这些文件以确定项目状态。

## 工作流

1. **创建**: 使用 `to-issues` 在 `.scratch/` 的相应子目录下创建新的 Markdown 文件。
2. **更新**: 修改文件内容或 Frontmatter 以反映进度。
3. **关闭**: 将文件移至 `closed/` 子目录，或更新 Frontmatter 中的 `status` 字段。
