# 提交记录模板

此文件用于记录每次 Git 提交的详细信息，便于长期追踪和审计。

---

## [<YYYY-MM-DD> <HH:MM>] <Commit-Type>: <简短描述>

### 📝 完整提交信息

```
<commit-hash>
<commit-message>
```

### 🎯 修改目的

<说明本次提交的目的：实现了什么功能、修复了什么问题、为什么需要这个修改>

### 📋 修改内容

- <修改点 1>
- <修改点 2>
- <修改点 3>

### 📁 修改文件清单

| 文件路径 | 修改类型 | 主要变更 |
|---------|---------|---------|
| `path/to/file1.ts:123` | 修改 | 添加了 XXX 函数 |
| `path/to/file2.py:45-67` | 修改 | 修复了 YYY bug |
| `path/to/file3.js` | 新增 | 实现了 ZZZ 功能 |
| `path/to/file4.py` | 删除 | 移除了废弃的代码 |

### 📊 变更统计

```
<git diff --stat 输出>
```

### 🔗 关联信息

- Issue: <关联的 Issue 编号>
- PR: <关联的 PR 编号>
- Dependent: <依赖的其他提交>

### ⚠️ 注意事项

<如果有需要注意的事项，如数据库迁移、环境变量配置等，在此说明>

---

## 使用示例

## [2025-01-07 14:30] feat: 添加用户认证功能

### 📝 完整提交信息

```
a1b2c3d
feat(auth): add JWT token authentication

Implement JWT-based authentication system with refresh
token support for improved security and user experience.
```

### 🎯 修改目的

实现基于 JWT 的用户认证系统，替代原有的 session 认证方式，提高系统的安全性和可扩展性。

### 📋 修改内容

- 创建 AuthService 处理 JWT token 生成和验证
- 添加 `/api/auth/login` 和 `/api/auth/refresh` 端点
- 实现认证中间件保护受保护路由
- 更新前端登录组件支持 token 存储
- 添加 token 自动刷新机制

### 📁 修改文件清单

| 文件路径 | 修改类型 | 主要变更 |
|---------|---------|---------|
| `backend/app/services/auth.py:1-150` | 新增 | 创建认证服务 |
| `backend/app/api/auth.py:1-80` | 新增 | 添加认证 API 端点 |
| `backend/app/middleware/auth.py:1-50` | 新增 | 实现认证中间件 |
| `frontend/src/stores/auth.ts:10-45` | 修改 | 添加 token 存储逻辑 |
| `frontend/src/api/index.ts:5-15` | 修改 | 配置 Axios 拦截器 |
| `frontend/src/views/Login.vue:78-120` | 修改 | 更新登录处理逻辑 |

### 📊 变更统计

```
 backend/app/services/auth.py      | 150 +++++++++++++++++++++
 backend/app/api/auth.py           |  80 +++++++++++
 backend/app/middleware/auth.py    |  50 +++++++
 frontend/src/stores/auth.ts       |  35 ++++--
 frontend/src/api/index.ts         |  10 +-
 frontend/src/views/Login.vue      |  42 +++---
 6 files changed, 347 insertions(+), 20 deletions(-)
```

### 🔗 关联信息

- Issue: #42
- PR: #156
- Dependent: commit `f3e4d5c` (添加 PostgreSQL 用户表)

### ⚠️ 注意事项

- 需要配置环境变量 `JWT_SECRET_KEY`
- 需要运行数据库迁移创建 `users` 表
- 前端需要更新 `.env` 配置 API 地址
