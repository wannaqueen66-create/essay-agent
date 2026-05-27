from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CONFIG = os.path.join(ROOT_DIR, "config.essay-agent.yaml")


def latest_file(pattern: str) -> str:
    matches = glob.glob(pattern)
    if not matches:
        return ""
    return max(matches, key=lambda path: os.path.getmtime(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run essay-agent and sync its output to Supabase.")
    parser.add_argument("--config", default=os.getenv("ESSAY_AGENT_CONFIG", DEFAULT_CONFIG))
    parser.add_argument("--skip-run", action="store_true", default=False)
    parser.add_argument("--skip-supabase", action="store_true", default=False)
    parser.add_argument("--no-embeddings", action="store_true", default=False)
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    active_config = os.path.join(ROOT_DIR, "config.yaml")
    backup_config = os.path.join(ROOT_DIR, ".config.daily-paper-reader.backup.yaml")
    had_existing_config = os.path.exists(active_config)

    if not os.path.exists(config_path):
        raise FileNotFoundError(config_path)

    if not args.skip_run:
        if had_existing_config:
            shutil.copyfile(active_config, backup_config)
        shutil.copyfile(config_path, active_config)
        try:
            subprocess.run([sys.executable, os.path.join(ROOT_DIR, "src", "essay_agent_core.py")], check=True)
        finally:
            if had_existing_config and os.path.exists(backup_config):
                shutil.copyfile(backup_config, active_config)
                os.remove(backup_config)

    output_dir = os.getenv("ESSAY_AGENT_OUTPUT_DIR", os.path.join(ROOT_DIR, "output"))
    today = datetime.now().strftime("%Y-%m-%d")
    stats_path = latest_file(os.path.join(output_dir, f"essay_daily_{today}_stats.json"))

    if not args.skip_supabase:
        cmd = [
            sys.executable,
            os.path.join(ROOT_DIR, "src", "essay_agent_supabase.py"),
            "--db",
            os.getenv("ESSAY_AGENT_DB_PATH", os.path.join(ROOT_DIR, "papers.db")),
        ]
        if stats_path:
            cmd.extend(["--stats", stats_path])
        if args.no_embeddings:
            cmd.append("--no-embeddings")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
