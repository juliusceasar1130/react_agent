# Docker 容器网络与外部服务访问指南

修改时间: 2026-04-02 00:00 Asia/Shanghai

主要修改内容:
- 沉淀本次 `backend`、PostgreSQL、Milvus 与宿主机 API 之间的容器网络排查结论
- 说明 `external network`、`host.docker.internal`、容器名访问三种常见寻址方式的适用边界
- 记录 `savedatabase_app-network` 与 `savedatabase_app_network` 命名不一致的真实易错点
- 提供后续接入新数据库或宿主机服务时可复用的检查清单与标准做法

## 1. 背景

当前项目的后端既会访问同网络中的 PostgreSQL 容器，也会在 `RAG_BACKEND=milvus_hybrid` 时访问 Milvus；同时，部分模型服务和 Embedding 服务又运行在宿主机上，而不在当前 Compose 编排内。

这类“容器访问容器 + 容器访问宿主机服务”混合场景最容易出错的地方，不在代码逻辑本身，而在地址写法和网络边界判断。一旦把 `localhost`、容器名、外部网络名混用，就会出现“配置看起来都对，但容器就是连不上”的问题。

## 2. 这套方案解决什么问题

- 解决容器内 `localhost` 指向错误对象的问题
- 解决不同 `docker-compose.yml` 之间跨项目互访的网络接入问题
- 解决 Milvus 使用容器名访问时必须处于同一 Docker 网络的判断问题
- 解决 `external: true` 场景下网络名必须精确匹配的易错点
- 为后续接入 Ollama、`llama.cpp`、Milvus、PostgreSQL 等服务提供统一判断准则

## 3. 整体设计

这次实现采用了“3 类地址边界”：

1. 同一 Docker 网络中的容器互访
2. 容器访问宿主机上的服务
3. 宿主机本地程序访问宿主机上的服务

这个分层的关键思想是：
**先判断服务实际跑在哪里，再决定地址写法；不要先写地址，再反推网络。**

## 4. 核心调用链 / 执行流

1. 后端容器启动后，从环境变量读取 `RAG_BACKEND` 和 `MILVUS_URI`。
2. 当 `RAG_BACKEND='milvus_hybrid'` 时，后端通过 `settings.milvus_uri` 创建 Milvus 检索器。
3. 如果 `MILVUS_URI` 写成 `http://milvus-standalone:19530`，则要求后端容器与 `milvus-standalone` 位于同一 Docker 网络。
4. 如果外部模型服务运行在宿主机，例如 Ollama 或 `llama.cpp`，则容器应通过 `http://host.docker.internal:<port>` 访问，而不是 `localhost`。
5. 如果当前程序不是跑在容器里，而是直接在宿主机本地运行，才应继续使用 `http://localhost:<port>`。

已确认的代码与配置依据：

- `backend/app/config.py` 读取 `RAG_BACKEND` 和 `MILVUS_URI`
- `backend/app/agent/vector/factory.py` 通过 `settings.milvus_uri` 创建 Milvus 检索器
- `.env_docker` 已采用 `MILVUS_URI='http://milvus-standalone:19530'`
- `.env_docker` 中宿主机 API 已采用 `host.docker.internal`

## 5. 分层职责说明

### 5.1 外部网络层

入口文件：

- `docker-compose.yml`
- `docker0000/docker-compose.yml`

职责：

- 让不同 Compose 项目中的容器加入同一个已存在的外部网络
- 为跨 Compose 的数据库、后端、Milvus 互访提供统一 DNS 范围

为什么这样设计：

- PostgreSQL 与 agent backend 不在同一份 Compose 文件时，单靠默认网络无法互访
- 使用 `external: true` 可以复用其他项目已创建的网络，而不是重复造一套网络

设计经验：

- `external network` 的 `name` 必须与 `docker network ls` 中的实际名字完全一致

### 5.2 容器内服务发现层

入口文件：

- `.env_docker`
- `docker0000/milvus_docker-compose.yml`

职责：

- 为同网络中的容器提供稳定地址，如 `120JPH_postgres`、`milvus-standalone`
- 让 `backend` 通过容器名而不是硬编码 IP 访问依赖服务

为什么这样设计：

- 容器名或 service 名在同网络内可被 Docker DNS 解析
- 相比写死 IP，更便于迁移和重启

设计经验：

- “能用容器名访问”这个前提，永远依赖“是否在同一个网络”

### 5.3 宿主机 API 访问层

入口文件：

- `.env_docker`

职责：

- 让容器访问宿主机上的 Ollama、`llama.cpp` 或其他本地 API

为什么这样设计：

- 对容器而言，`localhost` 指向容器自身，不是宿主机
- `host.docker.internal` 是容器访问宿主机服务的更合适入口

设计经验：

- “容器访问宿主机服务”默认先试 `host.docker.internal`，不要先写 `localhost`

## 6. 关键设计取舍

### 6.1 Milvus 通过容器名访问，而不是走宿主机回环

选择：

- 在容器部署场景中，优先让后端通过 `http://milvus-standalone:19530` 访问 Milvus

原因：

- 这更符合容器间直连模型
- 不依赖宿主机端口映射再绕回容器

收益：

- 配置更清晰
- 容器迁移时不容易受宿主机 IP 变化影响

代价：

- 必须保证两边加入同一个 Docker 网络

### 6.2 宿主机模型服务使用 `host.docker.internal`

选择：

- 容器访问宿主机 Ollama 或 Embedding API 时使用 `host.docker.internal`

原因：

- `localhost` 在容器内语义错误

收益：

- 地址语义明确，便于阅读和排障

代价：

- 依赖 Docker Desktop 或兼容实现；跨平台时需要重新确认

### 6.3 `external network` 名称以 Docker 实际结果为准

选择：

- 用 `docker network ls` 的真实网络名作为唯一权威来源

原因：

- Compose 内部别名与 Docker 最终网络名不是一回事
- `savedatabase_app-network` 和 `savedatabase_app_network` 在 Docker 看来是两个不同名字

收益：

- 避免因为一个字符差异导致容器根本没进到目标网络

代价：

- 每次跨项目复用网络前都要做一次实际核对

## 7. 实践中的关键经验

### 7.1 容器里的 `localhost` 几乎从来不是你以为的那个服务

现象：

- 把本地 `.env` 里的 `http://localhost:19530` 直接搬进容器环境后，后端无法连到 Milvus

原因：

- 容器里的 `localhost` 是容器自己，不是宿主机，也不是其他容器

经验结论：

- 先判断调用方是不是运行在容器里；如果是，再判断目标服务到底在宿主机还是另一个容器

### 7.2 Compose 里的网络别名不等于 Docker 里的最终网络名

现象：

- Compose 配置里写的是 `app-network`，但 `docker network ls` 看到的实际名字是 `savedatabase_app-network`

原因：

- Docker Compose 会基于 project name 和网络名生成最终资源名

经验结论：

- 排查跨 Compose 网络问题时，以 `docker network ls` 的输出为准，不要只看 YAML

### 7.3 让 Milvus 同时保留默认网络和外部网络是更稳妥的做法

现象：

- Milvus `standalone` 既要和 `etcd`、`minio` 通信，又要被 agent backend 访问

原因：

- `etcd`、`minio` 默认在当前 Milvus Compose 的默认网络里
- `backend` 在另一个外部网络里

经验结论：

- 给 `standalone` 同时挂载默认网络和外部网络，可以兼顾内部依赖与外部访问

## 8. 易错点 / 反模式

- 易错点 1：在容器环境沿用 `.env` 里的 `localhost`。后果是请求回到容器自身，导致连接失败。
- 易错点 2：把 `savedatabase_app-network` 和 `savedatabase_app_network` 当成同一个网络。后果是 `external network` 接入失败。
- 易错点 3：只修改 `MILVUS_URI`，但没有让 Milvus 容器加入同一网络。后果是容器名无法解析。
- 易错点 4：误以为 Compose 文件中的 `app-network` 就是 Docker 中的最终网络名。后果是排查方向错误。

## 9. 推荐复用模板 / 标准做法

当后续新增一个“容器需要访问的依赖服务”时，建议按下面顺序判断：

1. 先确认调用方运行在哪里。
   - 宿主机本地程序
   - 当前容器
   - 另一个容器
2. 再确认被访问服务运行在哪里。
   - 宿主机
   - 同一 Compose
   - 另一份 Compose
   - 远程服务器
3. 根据运行位置选择地址写法。
   - 宿主机程序访问宿主机服务：`localhost`
   - 容器访问宿主机服务：`host.docker.internal`
   - 容器访问同网络容器：服务名或容器名
   - 访问远程服务：固定 IP 或域名
4. 如果跨 Compose 通过容器名访问，先核对目标网络实际名称，再配置 `external: true`
5. 修改完成后，用实际容器运行环境验证，而不是只在宿主机验证

可直接复用的 Compose 片段示例：

```yaml
networks:
  app-network:
    external: true
    name: savedatabase_app-network
```

```yaml
services:
  standalone:
    networks:
      default:
      app-network:
        aliases:
          - milvus-standalone
```

## 10. 推荐检查清单

### Docker / 网络

- [ ] 已执行 `docker network ls`，确认真实网络名
- [ ] `external: true` 的 `name` 与真实网络名完全一致
- [ ] 需要跨 Compose 互访的容器都已加入同一个网络

### 环境变量

- [ ] 容器环境没有错误使用 `localhost` 指向宿主机或其他容器
- [ ] 宿主机 API 已按需使用 `host.docker.internal`
- [ ] Milvus、PostgreSQL 等容器互访地址使用容器名或服务名

### 代码 / 运行

- [ ] 已确认运行时实际读取的是 `.env` 还是 `.env_docker`
- [ ] 已确认后端代码实际使用 `settings.milvus_uri` 等环境变量
- [ ] 已在真实容器环境中验证一次联通性

### 文档 / 维护

- [ ] 在 README 或开发文档中补充新的访问方式说明
- [ ] 记录这次网络接入的具体时间与主要改动点

## 11. 示例

### 输入素材示例

- 开发讨论：后端检索时是否需要访问 Milvus，是否要加入统一网络
- 配置文件：`docker-compose.yml`、`docker0000/docker-compose.yml`、`docker0000/milvus_docker-compose.yml`、`.env`、`.env_docker`
- 验证结果：`docker network ls` 中实际存在的是 `savedatabase_app-network`

### 提炼后的手册结论示例

- 背景：后端容器需要同时访问 PostgreSQL、Milvus 和宿主机模型服务
- 关键设计：容器访问容器走同网络容器名，容器访问宿主机走 `host.docker.internal`
- 易错点：不要把 Compose 里的 `app-network` 别名误当成 Docker 里的最终网络名

## 12. 后续可选优化方向

- 为项目增加一份专门的 Docker 部署说明，统一解释 `.env` 与 `.env_docker` 的使用边界
- 增加一个简单的容器联通自检脚本，启动后自动检查 PostgreSQL、Milvus、宿主机 API 是否可达
- 在主 `docker-compose.yml` 中显式对齐实际外部网络名，避免手工误配
- 统一整理当前各类服务地址命名规范，减少 `localhost`、IP、容器名混用

## 13. 一句话总结

Docker 容器网络排障真正可复用的关键，不是记住某个固定地址，而是：
**先判断服务运行边界，再决定使用 `localhost`、`host.docker.internal` 还是容器名。**
