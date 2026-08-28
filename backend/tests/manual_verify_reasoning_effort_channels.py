"""
一次性验证脚本：探测 vLLM 对 reasoning_effort / thinking_level 两个通道的接受度。

背景：Phase 3 spec 的 thinking_level_map 假设 UI high -> reasoning_effort=xhigh，
但 vLLM 服务端 thinkingLevelMap 的合法输入键是 off/minimal/medium/high/max，
xhigh 是输出值而非输入键。本脚本直接探测 vLLM 实际行为。

用法: python backend/tests/manual_verify_reasoning_effort_channels.py
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

VLLM_BASE_URL = "http://192.168.3.26:8089/v1"
MODEL = "gpt-5-nano"
PROMPT = "1+1=? 只回答数字。"


def try_call(label: str, **kwargs) -> None:
    llm = ChatOpenAI(
        model=MODEL,
        api_key="sk-no-key-required",
        base_url=VLLM_BASE_URL,
        timeout=60,
        **kwargs,
    )
    try:
        resp = llm.invoke([HumanMessage(content=PROMPT)])
        print(f"[{label}] OK    -> {resp.content[:60]}")
    except Exception as e:
        print(f"[{label}] FAIL  -> {type(e).__name__}: {str(e)[:200]}")


def main() -> None:
    print(f"vLLM: {VLLM_BASE_URL}  model: {MODEL}\n")

    # ---- 通道 A: 顶层 reasoning_effort（OpenAI 兼容参数）----
    try_call("reasoning_effort=medium(Phase2已用)", reasoning_effort="medium")
    try_call("reasoning_effort=high(标准最大值)", reasoning_effort="high")
    try_call("reasoning_effort=xhigh(spec映射值)", reasoning_effort="xhigh")

    # ---- 通道 B: chat_template_kwargs.thinking_level（Qwen3 原生通道）----
    try_call(
        "thinking_level=medium(Qwen原生)",
        extra_body={"chat_template_kwargs": {"enable_thinking": True, "thinking_level": "medium"}},
    )
    try_call(
        "thinking_level=high(Qwen原生)",
        extra_body={"chat_template_kwargs": {"enable_thinking": True, "thinking_level": "high"}},
    )


if __name__ == "__main__":
    main()
