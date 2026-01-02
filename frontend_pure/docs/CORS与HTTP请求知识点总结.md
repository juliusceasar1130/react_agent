# CORS 与 HTTP 请求知识点总结

> 创建时间：2025-12-27

---

## 一、CORS（跨源资源共享）

### 1.1 什么是 CORS

CORS（Cross-Origin Resource Sharing）是一种**基于 HTTP 头的机制**，允许服务器标识除了它自己以外的其他源（域、协议或端口），浏览器应该允许从这些源加载资源。

### 1.2 为什么需要 CORS

**浏览器的同源策略**（Same-Origin Policy）默认阻止一个域名的网页向另一个域名发起 AJAX 请求。

#### 同源判断

```
http://localhost:8080
     ↓ 不同源
http://localhost:8000
```

虽然都是 `localhost`，但**端口不同**，浏览器视为不同源。

### 1.3 CORS 工作原理

```
┌─────────────┐                   ┌─────────────┐
│   浏览器      │                   │   服务器      │
│  (执法者)    │                   │  (规则制定者)  │
└──────┬──────┘                   └──────┬──────┘
       │                                 │
   ① 发起请求                           │
   (带 Origin: localhost:8080)           │
       │                                 │
       ├──────────────────────────────>  │
       │                                 │
       │  ② 返回响应                      │
       │<──────────────────────────────  │
       │ (带 Access-Control-Allow-Origin)│
       │                                 │
   ③ 浏览器检查响应头                      │
       │                                 │
   如果允许 → 数据交给 JavaScript           │
   如果拒绝 → 抛出 CORS 错误                │
```

### 1.4 关键点

| 组件 | 作用 |
|------|------|
| **浏览器** | 强制执行 CORS 策略，决定是否允许 JavaScript 访问响应数据 |
| **服务器** | 返回 `Access-Control-Allow-Origin` 等响应头，声明允许的策略 |

### 1.5 证明：服务器端本身不强制 CORS

用 `curl` 或 Postman 直接请求 API，**不会有 CORS 限制**：

```bash
# 这个请求不会受 CORS 影响
curl http://localhost:8000/api/chat/sessions
```

因为 `curl` 没有同源策略，它不检查 CORS 响应头。

### 1.6 常见响应头

| 响应头 | 作用 |
|--------|------|
| `Access-Control-Allow-Origin` | 允许的源（`*` 表示所有） |
| `Access-Control-Allow-Methods` | 允许的 HTTP 方法（GET, POST, PUT, DELETE 等） |
| `Access-Control-Allow-Headers` | 允许的请求头 |
| `Access-Control-Allow-Credentials` | 是否允许携带 Cookie |

---

## 二、前端服务器 vs 后端服务器

### 2.1 架构图

```
浏览器访问 http://localhost:8080
         ↓
前端服务器 (Python http.server) 返回 index.html
         ↓
浏览器加载页面后，执行 main.js
         ↓
main.js 中的 fetch() 请求 http://localhost:8000/api/chat/...
         ↓
后端服务器 (FastAPI) 返回 JSON 数据
```

### 2.2 当前项目架构

| 组件 | 端口 | 启动命令 | 作用 |
|------|------|----------|------|
| **前端服务器** | 8080 | `python -m http.server 8080` | 托管 HTML/CSS/JS 静态文件 |
| **后端服务器** | 8000 | `uvicorn backend.app.main:app --port 8000` | 提供 RESTful API 接口 |

### 2.3 前端服务器的作用

前端服务器（Python http.server）负责：
- 托管 `index.html`、`main.js`、`style.css` 等静态文件
- 响应浏览器的页面请求
- 将文件传送给浏览器渲染

**注意**：浏览器本身没有端口，8080 是前端服务器监听的端口。

---

## 三、CORS 配置（FastAPI）

### 3.1 本项目配置

```python
# backend/app/main.py (2025-12-27 修改)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有来源
    allow_credentials=True,   # 允许携带 Cookie
    allow_methods=["*"],      # 允许所有 HTTP 方法
    allow_headers=["*"],      # 允许所有请求头
)
```

### 3.2 配置选项对比

| 配置 | 安全性 | 适用场景 |
|------|--------|----------|
| `["*"]` | 低 | 开发测试阶段 |
| `["http://localhost:8080"]` | 高 | 本地开发，只允许前端访问 |
| `["https://example.com"]` | 高 | 生产环境，指定具体域名 |

### 3.3 更安全的配置示例

```python
# 只允许前端 8080 端口访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 四、HTTP 请求方法：fetch() vs axios

### 4.1 为什么使用 fetch() 而不是 axios？

| 特性 | fetch() | axios |
|------|---------|-------|
| 类型 | 浏览器**原生 API** | 第三方库 |
| 安装 | **无需安装** | 需要 npm 或 CDN |
| 大小 | 0 KB | ~15 KB |
| 项目要求 | 符合"纯三件套" | 违反"不使用额外组件" |

### 4.2 项目约束回顾

需求文档明确要求：
- **纯三件套实现**：index.html、main.js、style.css
- **不使用额外的组件**

**fetch()** 是浏览器内置功能，不是额外组件，符合要求。

### 4.3 代码对比

```javascript
// fetch() - 原生，无需引入
const response = await fetch(url);
const data = await response.json();

// axios - 需要引入库
<script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
const response = await axios.get(url);
const data = response.data;
```

### 4.4 axios 的优势

虽然本项目使用 fetch()，但 axios 有以下优势：
- 自动 JSON 转换（无需手动 `.json()`）
- 请求/响应拦截器
- 更好的错误处理
- 支持旧版浏览器
- 请求取消功能
- 并发请求处理

### 4.5 本项目中的 fetch() 使用示例

```javascript
// frontend_pure/main.js

// 获取所有会话
async function fetchSessions() {
    const response = await fetch(`${API_BASE}/sessions`);
    if (!response.ok) throw new Error('获取会话失败');
    return await response.json();
}

// 创建新会话
async function createSession(title = '新对话') {
    const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
    });
    if (!response.ok) throw new Error('创建会话失败');
    return await response.json();
}

// 删除会话
async function deleteSession(sessionId) {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'DELETE'
    });
    if (!response.ok) throw new Error('删除会话失败');
    return await response.json();
}
```

---

## 五、常见问题 FAQ

### Q1: CORS 是服务器端还是浏览器端起作用？

**A**: CORS 是**浏览器端**的安全机制，但需要服务器配合返回正确的响应头。

### Q2: 用 Postman/curl 请求 API 不会有 CORS 问题吗？

**A**: 是的。Postman/curl 不是浏览器，没有同源策略，不受 CORS 限制。

### Q3: 前端服务器是必需的吗？

**A**: 不是必需的，可以直接用浏览器打开 `file://` 协议访问 HTML，但：
- 部分浏览器限制 `file://` 协议的 AJAX 请求
- 不符合实际部署场景
- 建议使用 HTTP 服务器模拟真实环境

### Q4: 如何选择 CORS 配置？

**A**:
- 开发环境：`allow_origins=["*"]`
- 生产环境：指定具体域名，如 `allow_origins=["https://yourdomain.com"]`

---

## 六、参考资源

- [MDN - CORS](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/CORS)
- [MDN - Fetch API](https://developer.mozilla.org/zh-CN/docs/Web/API/Fetch_API)
- [Axios 文档](https://axios-http.com/)
