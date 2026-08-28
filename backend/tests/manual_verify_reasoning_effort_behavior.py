"""
行为级探测：reasoning_effort 是否真的改变 Qwen3 推理行为（Phase 3 矛盾验证）。

方法：
- 固定 enable_thinking=true，仅改变 reasoning_effort（none/low/medium/high/xhigh）
- 观察响应中是否出现 reasoning_content（思考内容）及其长度、响应耗时
- 若 vLLM 真正应用了 reasoning_effort，推理强度越高 → reasoning_content 越长

用法: python backend/tests/manual_verify_reasoning_effort_behavior.py
"""

import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

VLLM_BASE_URL = "http://192.168.3.26:8089/v1"
MODEL = "gpt-5-nano"
PROMPT = "比较 9.11 和 9.9 哪个数字更大？请说明推理过程。"


def probe(label: str, effort: str) -> None:
    llm = ChatOpenAI(
        model=MODEL,
        api_key="sk-no-key-required",
        base_url=VLLM_BASE_URL,
        timeout=120,
        reasoning_effort=effort,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )
    start = time.time()
    try:
        resp = llm.invoke([HumanMessage(content=PROMPT)])
        elapsed = time.time() - start
        rc = getattr(resp, "reasoning_content", None)
        if rc is None:
            rc = resp.additional_kwargs.get("reasoning_content", "")
        print(f"[{label}] OK    elapsed={elapsed:.1f}s reasoning_len={len(rc) if rc else 0} answer={str(resp.content)[:40]!r}")
    except Exception as e:
        print(f"[{label}] FAIL  -> {type(e).__name__}: {str(e)[:150]}")


def main() -> None:
    print(f"vLLM: {VLLM_BASE_URL}  model: {MODEL}\nPrompt: {PROMPT}\n")
    for effort in ["none", "low", "medium", "high", "xhigh"]:
        probe(f"reasoning_effort={effort}", effort)


if __name__ == "__main__":
    main()
