from __future__ import annotations

from src import essay_agent_core
from src.essay_agent_core import (
    analyze_paper,
    build_messages_url,
    extract_messages_text,
    extract_responses_text,
    fetch_arxiv_results,
    fetch_openalex_results,
    normalize_llm_api_mode,
)


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


def test_fetch_arxiv_results_returns_empty_after_rate_limit(monkeypatch):
    class _RateLimitedClient:
        def __init__(self, **_kwargs):
            pass

        def results(self, _search):
            raise RuntimeError("HTTP 429 too many requests")

    monkeypatch.setattr(essay_agent_core.arxiv, "Client", _RateLimitedClient)
    monkeypatch.setattr(essay_agent_core.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("ARXIV_RETRIES", "1")

    assert fetch_arxiv_results("cat:cs.HC", 5) == []


def test_llm_api_mode_aliases():
    assert normalize_llm_api_mode("responses") == "responses"
    assert normalize_llm_api_mode("messages_api") == "messages"
    assert normalize_llm_api_mode("chat") == "chat_completions"
    assert normalize_llm_api_mode(None) == "auto"


def test_build_messages_url_accepts_base_variants():
    assert build_messages_url("https://api.anthropic.com") == "https://api.anthropic.com/v1/messages"
    assert build_messages_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages"
    assert build_messages_url("https://api.anthropic.com/v1/messages") == "https://api.anthropic.com/v1/messages"


def test_extract_responses_text_from_output_shape():
    class _Response:
        def model_dump(self):
            return {
                "output": [
                    {"content": [{"type": "output_text", "text": "hello"}, {"type": "output_text", "text": "world"}]}
                ]
            }

    assert extract_responses_text(_Response()) == "hello\nworld"


def test_extract_messages_text_from_anthropic_shape():
    payload = {"content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]}
    assert extract_messages_text(payload) == "hello\nworld"
