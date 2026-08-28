# llama.cpp 与 LangChain 配置要点总结

修改时间: 2026-04-06 10:14 Asia/Shanghai
主要修改内容:
- 新增 `llama.cpp` OpenAI 兼容接口与 LangChain `ChatOpenAI` 的配置经验总结
- 补充 `BASE_URL`、协议、API Key、模型名、`max_tokens` 与检查清单
- 给出推荐的 `.env` 与 Python 示例配置

本文档用于沉淀在项目中接入 `llama.cpp` OpenAI-compatible 接口时的关键配置要点，避免因 `BASE_URL`、协议或 token 配置不当导致请求失败或返回空内容。

## 1. BASE_URL 格式

错误示例:

- `https://ip:port/v1/chat/completions`
- 含完整接口路径
- 尾部带空格

正确示例:

- `http://ip:port/v1`
- 只保留到 `/v1`
- 不要追加 `/chat/completions`
- 不要带尾部空格

说明:

- `ChatOpenAI` 会在 `base_url` 后自动拼接 `/chat/completions`
- 如果把完整接口路径传进去，最终请求地址可能会变成 `/v1/chat/completions/chat/completions`

## 2. 协议匹配

- `llama.cpp` 默认是 HTTP 服务，通常应使用 `http://`
- 只有在服务端明确启用了 SSL/TLS 时，才使用 `https://`
- 协议不匹配时，常见现象是连接失败、握手失败或超时

## 3. API Key

- `llama.cpp` 默认不校验 API Key
- 可以填写任意非空字符串，例如 `sk-no-key-required`
- 若后续反向代理层新增鉴权，再按代理层要求调整

## 4. 模型名称

- 模型名应与服务端暴露的 `model id` 完全一致
- 在当前 `llama.cpp` 部署方式下，通常表现为与加载的 GGUF 文件名一致
- 示例: `GLM-4.7-Flash-Q6_K.gguf`

建议:

- 若有疑问，以接口 `/v1/models` 返回的模型名为准

## 5. max_tokens 设置

- 推理模型（reasoning model）通常需要更大的 `max_tokens`
- 建议至少设置为 `512`
- 若值过小，可能出现“思考过程占满 token，最终 `content` 为空”或答案被截断的问题

## 6. LangChain 参数写法

推荐写法:

- 使用 `api_key`
- 使用 `base_url`

兼容性说明:

- 当前项目所用 `langchain_openai` 版本中，`openai_api_key` 与 `openai_api_base` 仍可兼容
- 但新代码更建议统一写成 `api_key` 与 `base_url`，可读性更好，也更贴近 OpenAI-compatible 接口语义

## 7. 最终推荐配置

`.env` 示例:

```bash
DEEPSEEK_API_KEY='sk-no-key-required'
DEEPSEEK_MODEL='GLM-4.7-Flash-Q6_K.gguf'
DEEPSEEK_BASE_URL='http://100.69.44.20:8089/v1'
```

Python 示例:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.deepseek_model,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    max_tokens=512,
)
```

如需补充稳定性参数，可继续加入:

```python
llm = ChatOpenAI(
    model=settings.deepseek_model,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    temperature=settings.agent_temperature,
    max_tokens=settings.agent_max_tokens,
    request_timeout=settings.llm_timeout,
    max_retries=settings.llm_max_retries,
)
```

## 8. 关键检查清单

- [ ] `BASE_URL` 以 `/v1` 结尾，不包含后缀接口路径
- [ ] `BASE_URL` 无尾部空格
- [ ] `http` / `https` 与服务器实际协议一致
- [ ] `API Key` 为非空字符串
- [ ] `max_tokens` 足够大，尤其是推理模型
- [ ] 模型名与服务端暴露的 `model id` 完全匹配

## 9. 常见结论

- 最容易出错的是把 `DEEPSEEK_BASE_URL` 配成完整的 `/chat/completions` 地址
- 本地 `llama.cpp` 大多数情况下应优先尝试 `http://.../v1`
- 若模型支持工具调用（tool calling），才更适合接入当前项目的 SQL Agent 工具链
