"""
决定性验证：reasoning_effort 放进 chat_template_kwargs（模板变量源）是否生效。

背景：用户提供 Qwen3.8 chat template 片段，模板读取 reasoning_effort 变量：
- 默认 xhigh（未定义时）
- high/max -> xhigh；medium/low 原样
- medium 不注入指令；low/xhigh 注入指令文字

Phase 2 YAML 中 reasoning_effort 放在 extra_body 顶层（非 chat_template_kwargs），
本脚本验证：模板变量通道（chat_template_kwargs.reasoning_effort）是否有行为差异。

用法: python backend/tests/manual_verify_template_effort_channel.py
"""

import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

VLLM_BASE_URL = "http://192.168.3.26:8089/v1"
MODEL = "gpt-5-nano"
PROMPT = "请设计一个用于制造业车间的新员工入职培训方案，给出要点。"


def probe(label: str, extra_body: dict) -> None:
    llm = ChatOpenAI(
        model=MODEL,
        api_key="sk-no-key-required",
        base_url=VLLM_BASE_URL,
        timeout=120,
        extra_body=extra_body,
    )
    start = time.time()
    try:
        resp = llm.invoke([HumanMessage(content=PROMPT)])
        elapsed = time.time() - start
        content = str(resp.content)
        print(f"[{label}] elapsed={elapsed:.1f}s len={len(content)} 前60字: {content[:60]!r}")
    except Exception as e:
        print(f"[{label}] FAIL  -> {type(e).__name__}: {str(e)[:150]}")


def main() -> None:
    print(f"vLLM: {VLLM_BASE_URL}  model: {MODEL}\nPrompt: {PROMPT}\n")
    # 基线：不传 reasoning_effort（模板默认 xhigh）
    probe("不传(模板默认xhigh)", {"chat_template_kwargs": {"enable_thinking": True}})
    # 模板变量通道
    probe("effort=low(模板内)", {"chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "low"}})
    probe("effort=medium(模板内)", {"chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "medium"}})
    probe("effort=xhigh(模板内)", {"chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "xhigh"}})


if __name__ == "__main__":
    main()
