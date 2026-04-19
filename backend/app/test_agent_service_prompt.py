from types import SimpleNamespace

from backend.app.agent.service import _build_system_prompt


def test_system_prompt_requires_explicit_chart_guidance() -> None:
    prompt = _build_system_prompt(SimpleNamespace(dialect="sqlite"))

    assert "当结果属于时间趋势、分类对比、Top N 排名或双指标对比时" in prompt
    assert "必须明确提醒用户这组结果可以生成图表" in prompt
    assert "你可以直接回复“生成图表”、“生成趋势图”或“生成柱状图”" in prompt
    assert "不要只用“是否需要进一步分析”" in prompt


def test_system_prompt_requires_category_split_for_multi_series_chart() -> None:
    prompt = _build_system_prompt(SimpleNamespace(dialect="sqlite"))

    assert "build_chart_artifact 的 series 只允许这些键" in prompt
    assert "不要使用 metric、label、type、axis 等自定义键" in prompt
    assert "如果图表要对比多个车型、缺陷类型或其他分类" in prompt
    assert "不要只重复引用同一个 field 作为多条系列" in prompt
    assert "必须为每条系列补充 category_field/category_value" in prompt
    assert "或至少在系列名称里包含可识别的分类值" in prompt
