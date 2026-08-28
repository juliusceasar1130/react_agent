"""
行为级探测 2：Qwen3 原生通道 chat_template_kwargs.thinking_level 是否生效。

对比：
- thinking_level=off  vs  high（enable_thinking 恒为 true）
- 观察 reasoning_content 是否存在、耗时差异

若原生通道也无差异 → vLLM 部署本身未开启 reasoning 支持，Phase 3 前提不成立。

用法: python backend/tests/manual_verify_thinking_level_channel.py
"""

import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

VLLM_BASE_URL = "http://192.168.3.26:8089/v1"
MODEL = "gpt-5-nano"
PROMPT = "比较 9.11 和 9.9 哪个数字更大？请说明推理过程。"


def probe(label: str, thinking_level: str) -> None:
    llm = ChatOpenAI(
        model=MODEL,
        api_key="sk-no-key-required",
        base_url=VLLM_BASE_URL,
        timeout=120,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": True,
                "thinking_level": thinking_level,
            }
        },
    )
    start = time.time()
    try:
        resp = llm.invoke([HumanMessage(content=PROMPT)])
        elapsed = time.time() - start
        rc = getattr(resp, "reasoning_content", None)
        if rc is None:
            rc = resp.additional_kwargs.get("reasoning_content", "")
        print(f"[thinking_level={thinking_level}] OK    elapsed={elapsed:.1f}s reasoning_len={len(rc) if rc else 0} answer={str(resp.content)[:50]!r}")
    except Exception as e:
        print(f"[thinking_level={thinking_level}] FAIL  -> {type(e).__name__}: {str(e)[:150]}")


def main() -> None:
    print(f"vLLM: {VLLM_BASE_URL}  model: {MODEL}\nPrompt: {PROMPT}\n")
    for level in ["off", "minimal", "medium", "high", "max"]:
        probe(level, level)


if __name__ == "__main__":
    main()
