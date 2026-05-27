from __future__ import annotations

from src.essay_agent_core import analyze_paper


class _FailingChatCompletions:
    def create(self, **_kwargs):
        raise RuntimeError("model unavailable")


class _FailingChat:
    completions = _FailingChatCompletions()


class _FailingClient:
    chat = _FailingChat()


def test_analyze_paper_failure_returns_structured_result_without_name_error():
    result = analyze_paper(
        _FailingClient(),
        "test-model",
        "Test paper",
        "Test abstract",
        retries=1,
        retry_delay=0,
    )

    assert result["分析状态"] == "failed"
    assert result["相关性分数"] == 0
    assert "与建筑/体育空间/疗愈环境研究相关性" in result
    assert "与建筑/体育空间研究相关性" in result
