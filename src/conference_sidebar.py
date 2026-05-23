#!/usr/bin/env python
"""将会议检索结果写入 docs/_sidebar.md 的 Conference Papers 分组。"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SIDEBAR_PATH = ROOT_DIR / "docs" / "_sidebar.md"
DEFAULT_DOCS_DIR = ROOT_DIR / "docs"
CONFERENCE_HEADING = "* Conference Papers\n"


def norm_text(value: Any) -> str:
    return str(value or "").strip()


def parse_conference_result_name(path: Path) -> Tuple[str, str]:
    name = path.name
    match = re.match(r"^conference-([a-z0-9-]+)-([0-9,-]+)\.supabase\.(?:llm|rerank|rrf)\.json$", name)
    if not match:
        raise ValueError(f"无法从会议结果文件名解析会议和年份：{path}")
    conference = match.group(1).upper()
    years = match.group(2).replace("-", ",")
    return conference, years


def build_conference_marker(conference: str, years: str) -> str:
    key = f"{norm_text(conference).lower()}-{norm_text(years).replace(',', '-')}"
    key = re.sub(r"[^a-z0-9-]+", "-", key).strip("-")
    return f"<!--dpr-conference:{key}-->"


def build_conference_label(conference: str, years: str) -> str:
    year_label = ", ".join(part.strip() for part in norm_text(years).split(",") if part.strip())
    return f"{norm_text(conference).upper()} {year_label}".strip()


def build_conference_key(conference: str, years: str) -> str:
    key = f"{norm_text(conference).lower()}-{norm_text(years).replace(',', '-')}"
    return re.sub(r"[^a-z0-9-]+", "-", key).strip("-") or "conference"


def slugify(value: str) -> str:
    text = norm_text(value).lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9-]+", "", text)
    return text.strip("-") or "paper"


def yaml_escape_value(value: Any) -> str:
    text = norm_text(value)
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", '"', "'", "\n", "[", "]", "{", "}", ",", "&", "*", "!", "|", ">", "%", "@", "`"]):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return text


def normalize_sidebar_tag(raw_tag: str) -> Tuple[str, str]:
    text = norm_text(raw_tag)
    if not text:
        return "", ""
    kind, sep, label = text.partition(":")
    if not sep:
        return "query", text
    kind = norm_text(kind).lower() or "query"
    if kind == "keyword":
        kind = "query"
    if kind not in {"keyword", "query", "paper", "other"}:
        kind = "other"
    label = norm_text(label)
    if kind == "query" and label.endswith(":composite"):
        label = label[: -len(":composite")].strip()
    return kind, label


def build_conference_paper_route(paper: Dict[str, Any], conference: str, years: str) -> str:
    paper_id = norm_text(paper.get("id")) or "paper"
    title_slug = slugify(norm_text(paper.get("title")) or paper_id)
    basename = f"{slugify(paper_id)}-{title_slug}"
    return f"conference/{build_conference_key(conference, years)}/{basename}"


def get_evidence(ranked_item: Dict[str, Any]) -> str:
    return norm_text(
        ranked_item.get("canonical_evidence")
        or ranked_item.get("evidence_cn")
        or ranked_item.get("evidence_en")
        or ranked_item.get("tldr_cn")
        or ranked_item.get("tldr_en")
    )


def get_tldr(ranked_item: Dict[str, Any]) -> str:
    return norm_text(ranked_item.get("tldr_cn") or ranked_item.get("tldr_en"))


def ensure_sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", norm_text(value)).strip()
    if not text:
        return ""
    if text[-1] in ".。！？!?":
        return text
    return text + "。"


def first_sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", norm_text(value)).strip()
    if not text:
        return ""
    match = re.search(r"(.+?[。！？!?]|.+?\.(?:\s|$))", text)
    return norm_text(match.group(1)) if match else text[:180].strip()


def build_glance_fields(paper: Dict[str, Any], ranked_item: Dict[str, Any]) -> Dict[str, str]:
    title = norm_text(paper.get("title")) or "该论文"
    evidence = get_evidence(ranked_item)
    tldr = get_tldr(ranked_item) or evidence
    query_text = norm_text(ranked_item.get("matched_query_text"))
    return {
        "tldr": ensure_sentence(tldr or f"{title} 是一篇会议检索命中的相关论文"),
        "motivation": ensure_sentence(
            norm_text(ranked_item.get("motivation_cn")) or evidence or "本文关注会议检索需求中的相关研究问题"
        ),
        "method": ensure_sentence(
            norm_text(ranked_item.get("method_cn")) or "方法细节请参考摘要与 OpenReview 原文"
        ),
        "result": ensure_sentence(
            norm_text(ranked_item.get("result_cn")) or tldr or evidence or "结果与实验结论请参考摘要与原文"
        ),
        "conclusion": ensure_sentence(
            norm_text(ranked_item.get("conclusion_cn"))
            or (f"该论文与检索需求“{query_text}”相关" if query_text else "该论文与当前会议检索需求相关")
        ),
    }


def build_conference_summary_lines(
    paper: Dict[str, Any],
    ranked_item: Dict[str, Any],
    link: str,
) -> List[str]:
    evidence = get_evidence(ranked_item)
    tldr = get_tldr(ranked_item)
    query_text = norm_text(ranked_item.get("matched_query_text"))
    abstract = norm_text(paper.get("abstract"))
    source = norm_text(paper.get("source"))

    lines = [
        "---",
        "",
        "## 论文详细总结（自动生成）",
        "",
        "### 1. 检索相关性",
        ensure_sentence(evidence or "该论文由会议检索链路召回，具体相关性可结合检索需求和原文进一步判断"),
        "",
        "### 2. 核心内容",
        ensure_sentence(tldr or first_sentence(abstract) or "核心内容请参考摘要与 OpenReview 原文"),
        "",
        "### 3. 对应检索需求",
        ensure_sentence(query_text or "当前结果未记录具体命中的检索需求"),
        "",
        "### 4. 来源与原文",
    ]
    if source:
        lines.append(f"- Source：{source}")
    if link:
        lines.append(f"- OpenReview：[{link}]({link})")
    if not source and not link:
        lines.append("- 来源信息未记录。")
    lines.append("")
    return lines


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def score_from_ranked_item(item: Dict[str, Any]) -> float:
    for key in ("score", "star_rating"):
        try:
            return float(item.get(key))
        except Exception:
            continue
    return 0.0


def collect_ranked_ids(data: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    papers = data.get("papers") if isinstance(data.get("papers"), list) else []
    paper_ids = [norm_text(p.get("id")) for p in papers if isinstance(p, dict) and norm_text(p.get("id"))]
    llm_ranked = data.get("llm_ranked") if isinstance(data.get("llm_ranked"), list) else []
    ranked: List[Dict[str, Any]] = []
    seen = set()

    for item in llm_ranked:
        if not isinstance(item, dict):
            continue
        paper_id = norm_text(item.get("paper_id"))
        if not paper_id or paper_id in seen:
            continue
        seen.add(paper_id)
        ranked.append(item)

    if not ranked:
        queries = data.get("queries") if isinstance(data.get("queries"), list) else []
        merged: Dict[str, Dict[str, Any]] = {}
        for query in queries:
            if not isinstance(query, dict):
                continue
            for item in query.get("ranked") or []:
                if not isinstance(item, dict):
                    continue
                paper_id = norm_text(item.get("paper_id"))
                if not paper_id:
                    continue
                current = merged.get(paper_id)
                if current is None or score_from_ranked_item(item) > score_from_ranked_item(current):
                    merged[paper_id] = item
        ranked = sorted(merged.values(), key=score_from_ranked_item, reverse=True)

    if not ranked:
        ranked = [{"paper_id": paper_id} for paper_id in paper_ids]

    if limit > 0:
        ranked = ranked[:limit]
    return ranked


def build_sidebar_payload(
    paper: Dict[str, Any],
    ranked_item: Dict[str, Any],
    conference: str,
    years: str,
) -> str:
    title = norm_text(paper.get("title")) or norm_text(ranked_item.get("paper_id")) or "Untitled"
    link = norm_text(paper.get("link")) or "#"
    score = ranked_item.get("score", ranked_item.get("star_rating", "-"))
    try:
        score_text = f"{float(score):.1f}"
    except Exception:
        score_text = norm_text(score) or "-"
    tags = [
        {"kind": "paper", "label": conference.upper()},
        {"kind": "paper", "label": years.replace(",", "/")},
    ]
    matched_tag = norm_text(ranked_item.get("matched_query_tag"))
    if matched_tag:
        kind, label = normalize_sidebar_tag(matched_tag)
        if label:
            tags.append({"kind": kind or "query", "label": label})

    payload = {
        "title": title,
        "link": link,
        "score": score_text,
        "selection_source": "conference_retrieval",
        "tags": tags,
    }
    evidence = get_evidence(ranked_item)
    if evidence:
        payload["evidence"] = evidence
    return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)


def build_conference_markdown(
    paper: Dict[str, Any],
    ranked_item: Dict[str, Any],
    conference: str,
    years: str,
) -> str:
    title = norm_text(paper.get("title")) or norm_text(ranked_item.get("paper_id")) or "Untitled"
    title_zh = norm_text(ranked_item.get("title_zh") or paper.get("title_zh"))
    authors = paper.get("authors") if isinstance(paper.get("authors"), list) else []
    authors_text = ", ".join(norm_text(item) for item in authors if norm_text(item)) or "Unknown"
    published = norm_text(paper.get("published"))[:10] or "Unknown"
    source = norm_text(paper.get("source"))
    link = norm_text(paper.get("link"))
    abstract = norm_text(paper.get("abstract")) or "No abstract is available."
    evidence = get_evidence(ranked_item)
    tldr = get_tldr(ranked_item)
    glance = build_glance_fields(paper, ranked_item)
    score = ranked_item.get("score", ranked_item.get("star_rating", ""))
    try:
        score_text = f"{float(score):.1f}"
    except Exception:
        score_text = norm_text(score)

    tags = [f"paper:{conference.upper()}", f"paper:{years.replace(',', '/')}"]
    matched_tag = norm_text(ranked_item.get("matched_query_tag"))
    if matched_tag:
        kind, label = normalize_sidebar_tag(matched_tag)
        if label:
            tags.append(f"{kind}:{label}")

    lines = ["---"]
    lines.append(f"title: {yaml_escape_value(title)}")
    if title_zh:
        lines.append(f"title_zh: {yaml_escape_value(title_zh)}")
    lines.append(f"authors: {yaml_escape_value(authors_text)}")
    lines.append(f"date: {yaml_escape_value(published)}")
    if link:
        lines.append(f"pdf: {yaml_escape_value(link)}")
    lines.append(f"tags: [{', '.join(yaml_escape_value(tag) for tag in tags)}]")
    if score_text:
        lines.append(f"score: {score_text}")
    if evidence:
        lines.append(f"evidence: {yaml_escape_value(evidence)}")
    if tldr:
        lines.append(f"tldr: {yaml_escape_value(tldr)}")
    if source:
        lines.append(f"source: {yaml_escape_value(source)}")
    lines.append("selection_source: conference_retrieval")
    lines.append(f"motivation: {yaml_escape_value(glance['motivation'])}")
    lines.append(f"method: {yaml_escape_value(glance['method'])}")
    lines.append(f"result: {yaml_escape_value(glance['result'])}")
    lines.append(f"conclusion: {yaml_escape_value(glance['conclusion'])}")
    lines.append("---")
    lines.append("")
    lines.append("## Abstract")
    lines.append(abstract)
    lines.append("")
    lines.extend(build_conference_summary_lines(paper, ranked_item, link))
    return "\n".join(lines)


def write_conference_docs(
    docs_dir: Path,
    papers: Dict[str, Dict[str, Any]],
    ranked: List[Dict[str, Any]],
    conference: str,
    years: str,
) -> Dict[str, str]:
    route_by_id: Dict[str, str] = {}
    for item in ranked:
        paper_id = norm_text(item.get("paper_id"))
        paper = papers.get(paper_id)
        if not paper:
            continue
        route = build_conference_paper_route(paper, conference, years)
        md_path = docs_dir / f"{route}.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(build_conference_markdown(paper, item, conference, years), encoding="utf-8")
        route_by_id[paper_id] = route
    return route_by_id


def build_conference_block(result_path: Path, docs_dir: Path, limit: int = 80) -> List[str]:
    data = load_json(result_path)
    conference, years = parse_conference_result_name(result_path)
    marker = build_conference_marker(conference, years)
    label = build_conference_label(conference, years)
    papers = {
        norm_text(item.get("id")): item
        for item in (data.get("papers") if isinstance(data.get("papers"), list) else [])
        if isinstance(item, dict) and norm_text(item.get("id"))
    }
    ranked = collect_ranked_ids(data, limit)
    route_by_id = write_conference_docs(docs_dir, papers, ranked, conference, years)

    lines = [f"  * {label} {marker}\n", "    * 推荐论文\n"]
    for item in ranked:
        paper_id = norm_text(item.get("paper_id"))
        paper = papers.get(paper_id)
        if not paper:
            continue
        title = norm_text(paper.get("title")) or paper_id
        route = route_by_id.get(paper_id) or build_conference_paper_route(paper, conference, years)
        href = f"#/{route}"
        payload = build_sidebar_payload(paper, item, conference, years)
        lines.append(
            "      * "
            f'<a class="dpr-sidebar-item-link dpr-sidebar-item-structured" href="{html.escape(href, quote=True)}" '
            f'data-sidebar-item="{payload}">{html.escape(title)}</a>\n'
        )
    return lines


def find_conference_heading(lines: List[str]) -> int:
    for idx, line in enumerate(lines):
        if line.strip() == "* Conference Papers":
            return idx
    return -1


def remove_existing_conference_block(lines: List[str], marker: str) -> None:
    heading_idx = find_conference_heading(lines)
    if heading_idx < 0:
        return
    block_idx = -1
    for idx in range(heading_idx + 1, len(lines)):
        if lines[idx].startswith("* "):
            break
        if marker in lines[idx]:
            block_idx = idx
            break
    if block_idx < 0:
        return
    end = block_idx + 1
    while end < len(lines):
        if lines[end].startswith("  * ") and not lines[end].startswith("    * "):
            break
        if lines[end].startswith("* "):
            break
        end += 1
    del lines[block_idx:end]


def ensure_conference_heading(lines: List[str]) -> int:
    heading_idx = find_conference_heading(lines)
    if heading_idx >= 0:
        return heading_idx

    daily_idx = -1
    for idx, line in enumerate(lines):
        if line.strip() == "* Daily Papers":
            daily_idx = idx
            break
    insert_idx = daily_idx if daily_idx >= 0 else len(lines)
    if insert_idx > 0 and lines[insert_idx - 1].strip():
        lines.insert(insert_idx, "\n")
        insert_idx += 1
    lines.insert(insert_idx, CONFERENCE_HEADING)
    return insert_idx


def update_sidebar_with_conference(
    sidebar_path: Path,
    result_path: Path,
    limit: int = 80,
    docs_dir: Path = DEFAULT_DOCS_DIR,
) -> None:
    sidebar_path.parent.mkdir(parents=True, exist_ok=True)
    lines = sidebar_path.read_text(encoding="utf-8").splitlines(keepends=True) if sidebar_path.exists() else []
    conference, years = parse_conference_result_name(result_path)
    marker = build_conference_marker(conference, years)
    remove_existing_conference_block(lines, marker)
    heading_idx = ensure_conference_heading(lines)
    block = build_conference_block(result_path, docs_dir=docs_dir, limit=limit)
    lines[heading_idx + 1:heading_idx + 1] = block
    sidebar_path.write_text("".join(lines), encoding="utf-8")


def choose_result_file(paths: Iterable[Path]) -> Path:
    existing = [p for p in paths if p and p.exists()]
    if not existing:
        raise FileNotFoundError("没有可用的会议结果文件。")
    priority = {".llm.json": 0, ".rerank.json": 1, ".rrf.json": 2}
    return sorted(
        existing,
        key=lambda p: next((rank for suffix, rank in priority.items() if p.name.endswith(suffix)), 9),
    )[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="更新 docs/_sidebar.md 的 Conference Papers 分组。")
    parser.add_argument("--result", action="append", default=[], help="会议结果 JSON，优先 llm，其次 rerank/rrf。可重复传入。")
    parser.add_argument("--sidebar", default=str(DEFAULT_SIDEBAR_PATH))
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR))
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    result_path = choose_result_file(Path(item) for item in args.result)
    update_sidebar_with_conference(
        Path(args.sidebar),
        result_path,
        limit=max(int(args.limit or 0), 0),
        docs_dir=Path(args.docs_dir),
    )
    print(f"[INFO] Conference sidebar updated: {args.sidebar} <- {result_path}", flush=True)


if __name__ == "__main__":
    main()
