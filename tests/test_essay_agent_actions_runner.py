import os
import unittest

from src import essay_agent_actions_runner


class EssayAgentActionsRunnerTests(unittest.TestCase):
    def test_infer_reader_date_from_output_final_json(self):
        path = os.path.join("output", "essay_daily_2026-05-28_final.json")
        self.assertEqual(essay_agent_actions_runner.infer_reader_date(path), "20260528")

    def test_infer_reader_date_from_archive_backup_path(self):
        path = os.path.join("archive", "essay-agent", "20260527", "essay_agent_papers.json")
        self.assertEqual(essay_agent_actions_runner.infer_reader_date(path), "20260527")


if __name__ == "__main__":
    unittest.main()
