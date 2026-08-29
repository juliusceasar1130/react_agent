"""
一次性验证脚本：证明采样参数真正到达 LLM 服务网络请求体（阶段 C §5.3 端到端验证；适用于 ninfer / vLLM 等 OpenAI 兼容后端）。

原理：
1. 复用阶段 A 的 profile_loader 加载 thinking/fast 两档参数组合
2. 通过中间件逻辑（get_sampling_profile → apply_profile_to_model_settings）构造 model_settings
3. 模拟 LangChain 框架的 request.model.bind(**model_settings) 绑定
4. 用自定义 httpx transport 拦截实际 HTTP 请求体并打印

用法: python backend/tests/manual_verify_sampling_request_body.py [thinking|fast] [--level low|medium|high]
"""

import json

import httpx

from backend.app.agent.config.profile_loader import (
    apply_profile_to_model_settings,
    get_sampling_profile,
)


class RecordingTransport(httpx.BaseTransport):
    """拦截并记录所有出站 HTTP 请求体。"""

    def __init__(self) -> None:
        super().__init__()
        self.captured: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # 复制并读取请求体（原始 body 只能读一次）
        body_bytes = request.read()
        if body_bytes:
            try:
                self.captured.append(json.loads(body_bytes))
            except Exception:
                self.captured.append({"__raw__": body_bytes.decode("utf-8", errors="replace")})
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 0,
                "model": request.url.path,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 端到端验证：采样参数实际到达 LLM 请求体")
    parser.add_argument("mode", nargs="?", default="thinking", choices=["thinking", "fast"],
                        help="思考模式：thinking 或 fast")
    parser.add_argument("--level", default=None, choices=["low", "medium", "high"],
                        help="Phase 3：thinking 档强度（仅 mode=thinking 时生效）")
    args = parser.parse_args()

    enable_thinking = args.mode == "thinking"
    thinking_level = args.level if enable_thinking else None
    level_desc = f" (thinking_level={thinking_level})" if thinking_level else ""

    # 1. 加载 profile 并应用（等价于中间件 _inject_thinking_config 的逻辑）
    profile = get_sampling_profile(enable_thinking, thinking_level)
    model_settings: dict = {}
    apply_profile_to_model_settings(model_settings, profile)
    print(f"[1] profile_loader 注入后的 model_settings{level_desc}:")
    print(json.dumps(model_settings, ensure_ascii=False, indent=2))

    # 2. 构造带自定义 transport 的 httpx client，捕获请求体
    recorder = RecordingTransport()
    client = httpx.Client(transport=recorder, base_url="http://127.0.0.1:9999/v1")

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model="gpt-5-nano",
        api_key="sk-no-key-required",
        base_url="http://127.0.0.1:9999/v1",
        http_client=client,
        timeout=30,
    )

    # 3. 模拟 LangChain 框架: request.model.bind(**request.model_settings)
    bound = llm.bind(**model_settings)

    from langchain_core.messages import HumanMessage

    bound.invoke([HumanMessage(content="你好")])

    # 4. 打印捕获到的网络请求体
    print("\n[2] 实际发往 LLM 服务的 HTTP 请求体（网络层捕获）:")
    for body in recorder.captured:
        print(json.dumps(body, ensure_ascii=False, indent=2))

    # 5. 断言验证
    assert recorder.captured, "未捕获到任何请求体！"
    body = recorder.captured[0]
    checks = {
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "presence_penalty": body.get("presence_penalty"),
        "top_k": body.get("top_k"),
        "enable_thinking": body.get("chat_template_kwargs", {}).get("enable_thinking"),
    }
    if enable_thinking:
        checks["reasoning_effort"] = body.get("reasoning_effort")
    print("\n[3] 参数核对:")
    for k, v in checks.items():
        print(f"  {k}: {v}")

    expected = {
        "temperature": 1.0 if enable_thinking else 0.7,
        "top_p": 0.95 if enable_thinking else 0.8,
        "presence_penalty": 0.0 if enable_thinking else 1.5,
        "top_k": 20,
        "enable_thinking": enable_thinking,
    }
    if enable_thinking:
        expected["reasoning_effort"] = {
            "low": "low",
            "medium": "medium",
            "high": "xhigh",
        }.get(thinking_level, "medium")
    for k, expected_v in expected.items():
        actual_v = checks[k]
        status = "✅" if actual_v == expected_v else "❌"
        print(f"  {status} {k}: 期望 {expected_v!r}, 实际 {actual_v!r}")
        assert actual_v == expected_v, f"{k} 不匹配: 期望 {expected_v}, 实际 {actual_v}"

    print("\n🎉 网络层验证通过：所有采样参数均正确到达请求体！")


if __name__ == "__main__":
    main()
