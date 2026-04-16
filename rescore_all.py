"""一次性批量重评分脚本。

用法:
    python rescore_all.py                  # 跑完所有 scoring_version != v2_multi 的论文
    python rescore_all.py --limit 100      # 只跑前 100 篇（按优先级）
    python rescore_all.py --version v2_multi --all  # 重跑所有论文（含 v2），强制刷新

优先级与 essay_agent 里的渐进式重评分一致：
  A. meets_threshold=1 AND displayed_at IS NULL
  B. meets_threshold=1 AND displayed_at 最近 14 天
  C. 其余
"""
import argparse
import logging
import os
import sys

from essay_agent import (
    SCORING_VERSION_V2,
    init_db,
    load_config,
    load_env,
    migrate_db,
    rescore_legacy_batch,
    select_legacy_rescore_candidates,
)

logger = logging.getLogger("rescore_all")


def _count_pending(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE (scoring_version IS NULL OR scoring_version != ?) "
        "AND analysis_status='success' AND english_abstract IS NOT NULL AND english_abstract != ''",
        (SCORING_VERSION_V2,),
    ).fetchone()
    return row[0] if row else 0


def main():
    parser = argparse.ArgumentParser(description="一次性重跑多 agent 评分")
    parser.add_argument("--limit", type=int, default=None, help="最多处理的论文数；不指定则处理完所有 legacy")
    parser.add_argument("--batch", type=int, default=30, help="每批次大小（便于观察进度）")
    parser.add_argument("--all", action="store_true", help="强制重跑所有论文（包括已经是 v2_multi 的）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = load_config("config.yaml")
    client, runtime = load_env()
    # 强制走 multi 模式
    runtime["scoring_mode"] = "multi"
    max_chars_per_paper = config.get("max_chars_per_paper", 6000)
    db_path = config.get("db_path", "papers.db")

    if not os.path.exists(db_path):
        logger.error("数据库不存在：%s", db_path)
        sys.exit(1)

    conn = init_db(db_path)
    migrate_db(conn)

    if args.all:
        logger.info("--all 模式：临时把所有 scoring_version 清空以触发重评分")
        conn.execute("UPDATE papers SET scoring_version=NULL WHERE analysis_status='success'")
        conn.commit()

    total_pending = _count_pending(conn)
    target = args.limit if args.limit is not None else total_pending
    logger.info("待重评分总数：%d；本次目标：%d；批次大小：%d", total_pending, target, args.batch)

    totals = {"picked": 0, "upgraded": 0, "downgraded": 0, "unchanged": 0, "failed": 0}
    processed = 0
    while processed < target:
        batch_limit = min(args.batch, target - processed)
        candidates = select_legacy_rescore_candidates(conn, batch_limit)
        if not candidates:
            logger.info("没有更多候选，结束。")
            break
        result = rescore_legacy_batch(
            conn=conn,
            client=client,
            runtime=runtime,
            limit=batch_limit,
            max_chars_per_paper=max_chars_per_paper,
        )
        for k in totals:
            totals[k] += result.get(k, 0)
        processed += result.get("picked", 0)
        logger.info("[进度] 已处理 %d / %d  批次结果=%s", processed, target, result)
        if result.get("picked", 0) == 0:
            break

    logger.info("=== 完成 === 累计：%s", totals)
    conn.close()


if __name__ == "__main__":
    main()
