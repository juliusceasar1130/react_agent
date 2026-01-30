# FastAPI 后端 Docker 部署指南

## 📋 部署架构

```
服务器
├── Docker Network: app-network
│   ├── PostgreSQL 容器 (已运行)
│   │   └── rearch-agent-postgres:5432
│   └── FastAPI Backend 容器
│       └── rearch-agent-backend:8000
└── Nginx (反向代理，可选)
```

**注意**：本配置假设 PostgreSQL 容器已经在运行，并且在 `app-network` 网络中。

---

## 🚀 快速部署

### 前置条件

1. **PostgreSQL 容器已运行**
   ```bash
   # 检查postgres容器状态
   docker ps | grep rearch-agent-postgres
   
   # 检查网络
   docker network ls | grep app-network
   ```

2. **确保 app-network 网络存在**
   ```bash
   # 如果不存在，创建网络
   docker network create app-network
   ```

---

### 1. 服务器准备

确保服务器已安装 Docker 和 Docker Compose：

```bash
# 检查Docker版本
docker --version
docker-compose --version
```

如未安装，参考 [Docker官方安装文档](https://docs.docker.com/engine/install/)

---

### 2. 上传项目文件

将以下文件上传到服务器（假设目录为 `/opt/rearch_agent`）：

```
/opt/rearch_agent/
├── backend/
│   ├── app/
│   ├── Dockerfile
│   └── .dockerignore
├── docker-compose.yml
├── requirements.txt
└── .env  (从 .env.production 复制并修改)
```

上传方式示例：
```bash
# 使用scp上传
scp -r d:/Python/workplace/rearch_agent user@your-server:/opt/

# 或使用Git
git clone your-repo /opt/rearch_agent
```

---

### 3. 配置环境变量

```bash
cd /opt/rearch_agent

# 复制配置模板
cp .env.production .env

# 编辑配置文件
nano .env
```

**必须修改的配置项：**
- `DATABASE_URL`: 默认配置指向 `rearch-agent-postgres` 容器
  - 如果你的postgres容器名不同，需要修改
  - 格式：`postgresql://用户名:密码@容器名:5432/数据库名`
- `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`: 填写你的LLM服务信息
- `OLLAMA_BASE_URL`: 如果使用外部Ollama服务

**数据库连接示例：**
```env
# 连接到postgres容器（推荐）
DATABASE_URL=postgresql://root:root@rearch-agent-postgres:5432/rearch_agent

# 或从宿主机连接（如果backend不在docker中运行）
# DATABASE_URL=postgresql://root:root@localhost:5432/rearch_agent
```

---

### 4. 启动服务

```bash
# 构建并启动后端服务（后台运行）
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

**预期输出：**
```
NAME                     STATUS         PORTS
rearch-agent-backend     Up             0.0.0.0:8000->8000/tcp
```

**验证网络连接：**
```bash
# 检查backend是否加入了app-network
docker network inspect app-network

# 应该能看到 rearch-agent-postgres 和 rearch-agent-backend 两个容器
```

---

### 5. 验证部署

```bash
# 测试后端API
curl http://localhost:8000/

# 预期返回
{"Hellosq111ee1":"FastAPI"}
```

---

## 🔧 常用管理命令

```bash
# 停止服务
docker-compose stop

# 启动服务
docker-compose start

# 重启服务
docker-compose restart backend

# 查看实时日志
docker-compose logs -f

# 进入容器调试
docker-compose exec backend bash
docker-compose exec postgres psql -U root -d rearch_agent

# 更新代码后重新部署
docker-compose up -d --build backend
```

---

## 🌐 Nginx 反向代理配置（可选）

如果需要通过域名访问，配置Nginx：

```nginx
# /etc/nginx/sites-available/rearch_agent

server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/rearch_agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 日志管理

```bash
# 查看最近100行日志
docker-compose logs --tail=100 backend

# 日志持久化配置（在docker-compose.yml中添加）
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 🔒 安全建议

1. **修改默认密码**：更改 `.env` 中的 `POSTGRES_PASSWORD`
2. **限制端口暴露**：生产环境不要暴露5432端口到公网
3. **使用HTTPS**：配置SSL证书（推荐Let's Encrypt）
4. **定期备份数据库**：
   ```bash
   docker-compose exec postgres pg_dump -U root rearch_agent > backup.sql
   ```

---

## 🐛 故障排查

### 问题1：容器无法启动

```bash
# 检查日志
docker-compose logs backend

# 常见原因：端口被占用
sudo lsof -i :8000
```

### 问题2：数据库连接失败

```bash
# 检查postgres容器状态
docker-compose ps postgres

# 测试数据库连接
docker-compose exec postgres psql -U root -d rearch_agent -c "SELECT 1;"
```

### 问题3：环境变量未生效

```bash
# 检查容器内的环境变量
docker-compose exec backend env | grep DATABASE_URL
```

---

## 📦 数据持久化

数据库数据存储在 Docker Volume `pgdata` 中，即使删除容器数据也不会丢失。

```bash
# 查看卷
docker volume ls

# 备份卷数据
docker run --rm -v rearch_agent_pgdata:/data -v $(pwd):/backup \
  alpine tar czf /backup/pgdata-backup.tar.gz /data
```

---

## 🔄 更新部署

```bash
# 1. 拉取最新代码
cd /opt/rearch_agent
git pull

# 2. 重新构建并启动
docker-compose up -d --build backend

# 3. 验证
curl http://localhost:8000/
```

---

## 📞 技术支持

遇到问题请检查：
1. Docker和Docker Compose版本是否满足要求
2. 环境变量配置是否正确
3. 网络和防火墙设置
4. 容器日志中的错误信息
