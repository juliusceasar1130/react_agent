# 约定式提交规范 (Conventional Commits)

## 规范

```bash
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## 强制要求

- type 和 description 是必需的
- type 后必须跟冒号和空格
- description 不能大写开头
- description 不能以句号结尾

## 类型详解

### Build: 构建系统

```
build: update webpack to v5.0
build: add docker build configuration
```

### Chore: 杂项

```
chore: update dependencies
chore: add .editorconfig
```

### Ci: CI 配置

```
ci: add GitHub Actions workflow
ci: fix deployment script
```

### Docs: 文档

```
docs: add README installation guide
docs(api): update authentication examples
```

### Feat: 新功能

```
feat: add user profile page
feat(api): add pagination support
```

### Fix: Bug 修复

```
fix: prevent memory leak in event handler
fix(auth): resolve token expiration issue
```

### Perf: 性能

```
perf: reduce initial load time by 50%
perf(database): add index to user_email column
```

### Refactor: 重构

```
refactor: simplify error handling
refactor(auth): extract login logic to service
```

### Style: 代码风格

```
style: format code with Prettier
style: convert tabs to spaces
```

### Test: 测试

```
test: add unit tests for UserService
test(auth): cover edge cases in login flow
```

## Scope（作用域）

可选的作用域标识，说明变更影响的模块：

```
feat(auth): add OAuth2 support
fix(database): resolve connection pool issue
docs(api): update authentication examples
```

常见作用域：
- auth, api, db, ui, config
- 组件名、模块名、功能名

## Breaking Changes（破坏性变更）

在 footer 中声明：

```
feat: remove deprecated API endpoints

The following endpoints have been removed:
- GET /api/v1/users
- POST /api/v1/login

BREAKING CHANGE: API v1 is no longer supported. Migrate to v2.
```

或简化形式：

```
feat(api)!: remove deprecated endpoints

BREAKING CHANGE: API v1 removed, migrate to v2
```

注意：`!` 在 type/scope 后表示引入破坏性变更

## Revert（回退）

```
revert: feat: add user profile feature

This reverts commit 1a2b3c4
```

## 完整示例

```
feat(api): add pagination support to list endpoints

Add cursor-based pagination to improve performance
for large datasets. The new approach uses an encrypted
cursor instead of numeric offsets.

- Add `cursor` and `limit` query parameters
- Return `next_cursor` in response metadata
- Update API documentation with examples

Closes #123
```

## 工具集成

### Commitlint 验证

```json
{
  "rules": {
    "type-enum": [2, "always", ["feat", "fix", "docs", "style", "test", "refactor"]],
    "type-case": [2, "always", "lower-case"],
    "type-empty": [2, "never"],
    "subject-empty": [2, "never"],
    "subject-case": [2, "always", "sentence-case"],
    "header-max-length": [2, "always", 72]
  }
}
```

### Husky 自动化

```json
{
  "husky": {
    "hooks": {
      "commit-msg": "commitlint -E HUSKY_GIT_PARAMS"
    }
  }
}
```

## 中文提交支持

如果团队使用中文，type 保持英文，description 使用中文：

```
feat: 添加用户头像上传功能
fix: 修复登录后重定向失败的问题
docs: 更新 API 接口文档
```
