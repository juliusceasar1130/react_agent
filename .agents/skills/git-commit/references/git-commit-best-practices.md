# Git 提交最佳实践

## 核心原则

1. **原子性**: 每次提交只做一件事
2. **可读性**: 提交信息清晰明了
3. **可追溯**: 能够理解为什么做出这个修改
4. **无破坏**: 不破坏历史记录

## Commit Message 结构

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | feat: 添加用户登录功能 |
| `fix` | 修复 bug | fix: 修复登录后重定向失败 |
| `docs` | 文档变更 | docs: 更新 API 文档 |
| `style` | 代码格式 | style: 统一缩进为 2 空格 |
| `refactor` | 重构 | refactor: 简化认证逻辑 |
| `perf` | 性能优化 | perf: 减少数据库查询次数 |
| `test` | 测试 | test: 添加登录单元测试 |
| `chore` | 构建/工具 | chore: 更新依赖版本 |

### Subject 主题

- 使用祈使句（"Add" 而非 "Added"）
- 首字母小写
- 不以句号结尾
- 限制在 50 字符以内

### Body 正文

- 说明"做什么"和"为什么"
- 每行限制在 72 字符
- 使用要点列出主要变更

### Footer 脚注

- 关联 Issue: `Closes #123`
- 破坏性变更: `BREAKING CHANGE:`
- 作者签名

## 示例

### 好的提交

```
feat(auth): add JWT token refresh mechanism

Implement automatic token refresh to improve user experience.
Tokens now refresh automatically 5 minutes before expiration.

Changes:
- Add refresh endpoint /api/auth/refresh
- Implement token expiry check middleware
- Update frontend to handle refresh logic

Closes #42
```

### 不好的提交

```
update
fixed bugs
wip
```

## 常见错误

1. **提交过于频繁**: 将相关变更分散到多个提交
2. **提交过于庞大**: 将不相关的变更合并在一个提交
3. **信息模糊**: "update", "fix", "changes" 等无意义描述
4. **提交敏感信息**: 密钥、配置文件等
5. **提交构建产物**: node_modules, __pycache__, .pyc 等

## .gitignore 必须包含

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# Node
node_modules/
dist/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# 环境变量
.env
.env.local
```

## 分支策略

- `master/main`: 生产环境
- `develop`: 开发环境
- `feature/*`: 功能开发
- `hotfix/*`: 紧急修复
- `release/*`: 发布准备
