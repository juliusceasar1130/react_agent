---
name: git-commit
description: 专业的 Git 提交助手。用于创建结构化的 Git 提交记录，自动记录修改的文件列表和主要修改内容，生成符合规范的 commit message。当用户需要提交代码、创建 commit 或记录代码变更时使用此技能。
version: 1.0.0
---

# Git Commit Skill

专业的 Git 代码提交助手，用于创建结构化、可追溯的提交记录。

## 使用场景

当以下情况时使用此 skill：
- 用户请求提交代码到 Git 仓库
- 需要创建 commit 并记录变更内容
- 需要生成符合规范的 commit message
- 需要记录本次提交涉及的所有文件和修改要点

## 工作流程

执行 Git 提交时，**必须严格遵循以下步骤**：

### 第一步：收集变更信息

并行执行以下命令获取完整变更状态：

```bash
git status                    # 查看工作区状态
git diff --stat              # 查看变更文件统计
git diff HEAD~1..HEAD --stat  # 查看与上一次提交的差异（如适用）
git log -1 --format='%an %ae' # 验证最近提交的作者（用于 amend 判断）
```

### 第二步：分析变更内容

根据收集的信息，分析并记录：

1. **修改文件列表**：完整的文件路径列表
2. **变更类型**：新增/修改/删除/重命名
3. **修改摘要**：每个文件的主要修改内容（简要描述）
4. **功能影响**：这些变更实现了什么功能或解决了什么问题

### 第三步：生成提交信息

使用以下模板生成结构化的 commit message：

```
<commit-type>: <brief-description>

## 主要变更

<列出主要的修改内容，使用要点形式>

## 修改文件

<列出所有涉及修改的文件>

---
📅 提交时间: <timestamp>
📝 修改说明: <detailed-explanation-if-needed>
```

**提交类型 (commit-type)** 包括：
- `feat`: 新功能
- `fix`: 修复 bug
- `refactor`: 重构代码
- `docs`: 文档变更
- `style`: 代码格式调整
- `test`: 测试相关
- `chore`: 构建/工具配置

### 第四步：执行提交

使用 `Bash` 工具执行 Git 命令：

```bash
# 添加相关文件到暂存区
git add <file-list>

# 创建提交（使用 HEREDOC 传递多行 commit message）
git commit -m "$(cat <<'EOF'
<commit-message-content>
EOF
)"

# 验证提交成功
git status
```

## 提交记录模板

创建一个 CHANGELOG 记录文件用于长期追踪：

```markdown
# 提交记录

## [<日期>] <Commit-Type>: <简短描述>

### 修改内容
- <修改点 1>
- <修改点 2>

### 修改文件
- `path/to/file1.ts:123` - 修改说明
- `path/to/file2.py:45-67` - 修改说明

### 影响范围
- <影响的模块/功能>
```

## 安全规则

- **永远不要**使用 `git commit --amend` 修改已推送的提交
- **永远不要**使用 `git push --force` 到公共分支
- 提交前确保不包含敏感信息（密钥、密码、token）
- 验证 `git log -1 --format='%an %ae'` 确认提交者
- 只有当前提交未推送且由当前会话创建时才允许 amend

## 特殊场景处理

### 修复失败的提交

如果提交失败（如 pre-commit hook 拒绝）：
1. 分析失败原因
2. 修复问题
3. 创建新的提交（不要 amend）
4. 记录两次提交的关联关系

### 部分暂存提交

对于需要分批提交的变更：
1. 使用 `git add -p` 交互式添加
2. 为每个逻辑单元创建独立提交
3. 在 commit message 中说明后续计划

## 输出格式

完成提交后，向用户输出：

```
✅ 提交成功！

📦 Commit: <commit-hash>
📝 消息: <commit-title>

📋 修改文件 (<count> 个):
<file-list>

📊 变更统计:
<git diff --stat output>
```

## 相关资源

- `references/git-commit-best-practices.md`: Git 提交最佳实践
- `references/conventional-commits.md`: 约定式提交规范
