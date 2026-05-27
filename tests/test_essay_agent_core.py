from __future__ import annotations

from src import essay_agent_core
from src.essay_agent_core import analyze_paper, fetch_openalex_results


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


class _OpenAlexResponse:
    def json(self):
        return {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": None,
                    "abstract_inverted_index": None,
                    "publication_date": "2026-05-28",
                    "authorships": [{"author": {"display_name": None}}],
                    "primary_location": None,
                    "primary_topic": None,
                    "concepts": [None, {"display_name": "Built environment"}],
                }
            ]
        }


def test_fetch_openalex_results_tolerates_null_title(monkeypatch):
    monkeypatch.setattr(
        essay_agent_core.requests,
        "get",
        lambda *_args, **_kwargs: _OpenAlexResponse(),
    )

    rows = fetch_openalex_results("sports space", 1)

    assert len(rows) == 1
    assert rows[0]["title"] == ""
    assert rows[0]["abstract"] == ""
    assert rows[0]["url"] == "https://openalex.org/W1"
