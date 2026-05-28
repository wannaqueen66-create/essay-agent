import json
import os
import tempfile
import unittest

from src import essay_agent_reader


class EssayAgentReaderTests(unittest.TestCase):
    def sample_rows(self):
        return [
            {
                "doi": "10.1000/low",
                "source": "openalex",
                "title": "Low score paper",
                "url": "https://example.test/low",
                "published_date": "2026-05-27",
                "authors": "A; B",
                "english_abstract": "Low abstract",
                "中文摘要": "低分摘要",
                "研究主题": "低分主题",
                "相关性分数": 61,
                "可借鉴启发": "低分启发",
            },
            {
                "doi": "10.1000/high",
                "source": "arxiv",
                "title": "High score paper",
                "url": "https://arxiv.org/abs/2605.00001v1",
                "published_date": "2026-05-28",
                "authors": ["C"],
                "english_abstract": "High abstract",
                "中文摘要": "高分摘要",
                "研究主题": "高分主题",
                "相关性分数": 92,
                "可借鉴启发": "高分启发",
            },
        ]

    def test_build_recommend_payload_sorts_and_splits(self):
        payload = essay_agent_reader.build_recommend_payload(
            self.sample_rows(),
            top_n=2,
            deep_top_n=1,
            date="20260528",
        )

        self.assertEqual(payload["deep_dive"][0]["title"], "High score paper")
        self.assertEqual(payload["deep_dive"][0]["llm_score"], 9.2)
        self.assertEqual(payload["deep_dive"][0]["pdf_url"], "https://arxiv.org/pdf/2605.00001v1")
        self.assertEqual(payload["quick_skim"][0]["title"], "Low score paper")

    def test_reader_id_is_stable_and_safe(self):
        first = essay_agent_reader.stable_reader_id(self.sample_rows()[0])
        second = essay_agent_reader.stable_reader_id(self.sample_rows()[0])

        self.assertEqual(first, second)
        self.assertRegex(first, r"^essay-agent-openalex-[a-f0-9]{12}$")

    def test_update_reader_index_maps_source_id_to_route(self):
        payload = essay_agent_reader.build_recommend_payload(
            self.sample_rows(),
            top_n=1,
            deep_top_n=1,
            date="20260528",
        )
        with tempfile.TemporaryDirectory() as tmp:
            index_path = os.path.join(tmp, "reader-index.json")
            essay_agent_reader.update_reader_index(payload, date8="20260528", index_path=index_path)
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)

        source_id = "doi:10.1000/high"
        self.assertIn(source_id, index["routes"])
        self.assertIn("202605/28/essay-agent-arxiv-", index["routes"][source_id])

    def test_route_slug_matches_generate_docs_behavior(self):
        route = essay_agent_reader.route_for_item(
            "20260528",
            {
                "id": "paper-1",
                "title": "A - B: Study",
            },
        )

        self.assertEqual(route, "202605/28/paper-1-a---b-study")

    def test_score_can_fallback_to_analysis_json(self):
        payload = essay_agent_reader.build_recommend_payload(
            [
                {
                    "source": "openalex",
                    "title": "Analysis score paper",
                    "link": "https://example.test/analysis-score",
                    "published": "2026-05-28T00:00:00+00:00",
                    "analysis": {"相关性分数": 87, "中文摘要": "摘要"},
                }
            ],
            top_n=1,
            deep_top_n=1,
            date="20260528",
        )

        self.assertEqual(payload["deep_dive"][0]["domain_relevance_score"], 87)
        self.assertEqual(payload["deep_dive"][0]["llm_score"], 8.7)


if __name__ == "__main__":
    unittest.main()
