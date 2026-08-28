"""
行为级验证：证明 vLLM 真正使用请求体中的采样参数。

方法：
- 同一 prompt、同一模型，仅改变 temperature（2.0 vs 0.0）
- 若 vLLM 真的应用了 temperature，输出应明显不同（高温度更发散、低温度更收敛）

用法: python backend/tests/manual_verify_vllm_behavior.py
"""

import sys
import time

import httpx

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

VLLM_BASE_URL = "http://192.168.3.26:8089/v1"
MODEL = "gpt-5-nano"
PROMPT = "用一句话描述一辆蓝色轿车在雨天的场景，不要重复。"


def invoke_with_temperature(temperature: float, seed: int | None = None) -> tuple[str, dict]:
    """用指定 temperature 调用 vLLM，返回输出文本和请求参数。"""
    kwargs: dict = {"temperature": temperature}
    if seed is not None:
        kwargs["seed"] = seed

    llm = ChatOpenAI(
        model=MODEL,
        api_key="sk-no-key-required",
        base_url=VLLM_BASE_URL,
        timeout=60,
        **kwargs,
    )
    start = time.time()
    resp = llm.invoke([HumanMessage(content=PROMPT)])
    elapsed = time.time() - start
    return resp.content, {"temperature": temperature, "elapsed": round(elapsed, 2)}


def main() -> None:
    print(f"vLLM: {VLLM_BASE_URL}  model: {MODEL}")
    print(f"Prompt: {PROMPT}")
    print("=" * 70)

    # 1. temperature=0.0（完全确定性的贪心采样，输出最收敛）
    out_cold, meta_cold = invoke_with_temperature(0.0)
    print(f"\n[1] temperature=0.0  ({meta_cold['elapsed']}s)")
    print(f"    输出: {out_cold}")

    # 2. temperature=2.0（高随机性，输出最发散）
    out_hot, meta_hot = invoke_with_temperature(2.0)
    print(f"\n[2] temperature=2.0  ({meta_hot['elapsed']}s)")
    print(f"    输出: {out_hot}")

    # 3. 同温度同 seed 重复调用（应输出一致 → 证明参数稳定传递）
    out_seed_a, _ = invoke_with_temperature(0.5, seed=42)
    out_seed_b, _ = invoke_with_temperature(0.5, seed=42)
    print(f"\n[3] temperature=0.5 seed=42 两次调用")
    print(f"    第一次: {out_seed_a}")
    print(f"    第二次: {out_seed_b}")
    seed_deterministic = out_seed_a == out_seed_b
    print(f"    输出一致: {'是' if seed_deterministic else '否'}")

    # 判定：冷热输出是否不同
    different = out_cold != out_hot
    print("\n" + "=" * 70)
    print(f"判定: temperature=0.0 与 temperature=2.0 输出不同 → {'✅ vLLM 确实应用了 temperature' if different else '❌ 输出相同，可能未应用 temperature'}")
    if not different:
        print("提示: 若相同，需检查 vLLM 是否忽略请求体中的采样参数（如 --enforce-eager 或请求解析问题）")


if __name__ == "__main__":
    main()
