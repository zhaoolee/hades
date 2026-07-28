"""Deterministic extraction, merge, audit, and rendering pipeline."""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .parsers import LuaCandidate, TextEntry, parse_lua_candidates, parse_sjson, parse_subtitle_csv

FIELDS = ["id", "channel", "speaker", "en", "zh", "status", "en_source", "zh_source"]


def validate_game_root(game_root: Path) -> Path:
    root = game_root.expanduser().resolve()
    required = [root / "Content/Subtitles/en", root / "Content/Subtitles/zh-CN",
                root / "Content/Game/Text/zh-CN", root / "Content/Scripts"]
    missing = [p.relative_to(root).as_posix() for p in required if not p.is_dir()]
    if missing:
        raise ValueError(f"invalid game root {game_root}: missing {', '.join(missing)}")
    return root


def _normal(value: str) -> str:
    value = re.sub(r"\{#[^}]*\}", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def choose_lua(dialogue_id: str, candidates: list[LuaCandidate], comment: str, issues: list[dict]) -> LuaCandidate | None:
    if not candidates:
        return None
    unique: list[LuaCandidate] = []
    seen = set()
    for candidate in candidates:
        if candidate.text and candidate.text not in seen:
            seen.add(candidate.text)
            unique.append(candidate)
    if len(unique) == 1:
        return unique[0]
    normalized_comment = _normal(comment)
    matches = [candidate for candidate in unique if _normal(candidate.text) in normalized_comment]
    if len(matches) == 1:
        chosen = matches[0]
        method = "sjson_comment"
    else:
        pool = matches or unique
        chosen = sorted(pool, key=lambda c: (c.fallback, c.source, c.offset, c.text))[0]
        method = "deterministic_fallback"
    issues.append({"kind": "lua_ambiguity", "id": dialogue_id, "candidate_count": len(unique),
                   "chosen": chosen.text, "method": method,
                   "candidates": [{"text": c.text, "source": c.source, "fallback": c.fallback} for c in unique]})
    return chosen


def build_records(csv_rows: dict[str, Any], sjson_rows: dict[str, TextEntry],
                  lua_candidates: dict[str, list[LuaCandidate]]) -> tuple[list[dict], list[dict]]:
    """Merge by ID. SJSON is authoritative for active Chinese and its Lua English."""
    issues: list[dict] = []
    ids = sorted(set(csv_rows) | set(sjson_rows))
    records: list[dict] = []
    for dialogue_id in ids:
        csv_item = csv_rows.get(dialogue_id, {})
        current = sjson_rows.get(dialogue_id)
        if current:
            chosen = choose_lua(dialogue_id, lua_candidates.get(dialogue_id, []), current.comment, issues)
            en = chosen.text if chosen else ""
            zh = current.text
            en_source = chosen.source if chosen else ""
            zh_source = current.source
            channel = current.channel or dialogue_id.split("_", 1)[0]
            speaker = current.speaker or channel
            if csv_item and ((isinstance(csv_item, dict) and csv_item.get("zh") != zh)):
                issues.append({"kind": "sjson_overrides_csv", "id": dialogue_id,
                               "csv_zh": csv_item.get("zh", ""), "sjson_zh": zh})
        else:
            if isinstance(csv_item, dict):
                en, zh = csv_item.get("en", ""), csv_item.get("zh", "")
                en_source, zh_source = csv_item.get("en_source", ""), csv_item.get("zh_source", "")
                channel = csv_item.get("channel", dialogue_id.split("_", 1)[0])
                speaker = csv_item.get("speaker", "") or channel
            else:
                en = zh = en_source = zh_source = ""
                channel = dialogue_id.split("_", 1)[0]
                speaker = channel
        status = "bilingual" if en and zh else "missing_en" if zh else "missing_zh" if en else "missing_both"
        records.append({"id": dialogue_id, "channel": channel, "speaker": speaker, "en": en, "zh": zh,
                        "status": status, "en_source": en_source, "zh_source": zh_source})
    return records, issues


def collect(game_root: Path) -> tuple[list[dict], dict]:
    root = validate_game_root(game_root)
    issues: list[dict] = []
    languages: dict[str, dict[str, TextEntry]] = {}
    csv_files: dict[str, list[str]] = {}
    for language in ("en", "zh-CN"):
        merged: dict[str, TextEntry] = {}
        files = sorted((root / "Content/Subtitles" / language).glob("*.csv"))
        csv_files[language] = [p.relative_to(root).as_posix() for p in files]
        for path in files:
            rows, found_issues = parse_subtitle_csv(path, language, root)
            issues.extend(found_issues)
            for dialogue_id, entry in rows.items():
                old = merged.get(dialogue_id)
                if old and old.text != entry.text:
                    preferred_channel = dialogue_id.split("_", 1)[0]
                    replace = entry.channel == preferred_channel and old.channel != preferred_channel
                    kept, discarded = (entry, old) if replace else (old, entry)
                    issues.append({"kind": "csv_cross_file_conflict", "language": language, "id": dialogue_id,
                                   "kept_source": kept.source, "discarded_source": discarded.source,
                                   "method": "id_prefix_channel" if kept.channel == preferred_channel
                                             else "deterministic_first"})
                    if replace:
                        merged[dialogue_id] = entry
                elif not old:
                    merged[dialogue_id] = entry
        languages[language] = merged
    csv_ids = sorted(set(languages["en"]) | set(languages["zh-CN"]))
    csv_rows: dict[str, dict] = {}
    for dialogue_id in csv_ids:
        en, zh = languages["en"].get(dialogue_id), languages["zh-CN"].get(dialogue_id)
        exemplar = en or zh
        csv_rows[dialogue_id] = {"en": en.text if en else "", "zh": zh.text if zh else "",
                                 "en_source": en.source if en else "", "zh_source": zh.source if zh else "",
                                 "channel": exemplar.channel if exemplar else dialogue_id.split("_", 1)[0],
                                 "speaker": (exemplar.channel if exemplar else dialogue_id.split("_", 1)[0])}

    sjson_rows: dict[str, TextEntry] = {}
    sjson_files = sorted((root / "Content/Game/Text/zh-CN").glob("_*.zh-CN.sjson"))
    for path in sjson_files:
        rows, found_issues = parse_sjson(path, root)
        issues.extend(found_issues)
        for dialogue_id, entry in rows.items():
            old = sjson_rows.get(dialogue_id)
            if old and old.text != entry.text:
                issues.append({"kind": "sjson_cross_file_conflict", "id": dialogue_id,
                               "kept_source": old.source, "discarded_source": entry.source})
            elif not old:
                sjson_rows[dialogue_id] = entry
    lua_files = sorted((root / "Content/Scripts").glob("*.lua"))
    lua = parse_lua_candidates(lua_files, root)
    records, merge_issues = build_records(csv_rows, sjson_rows, lua)
    issues.extend(merge_issues)
    missing_en = [r["id"] for r in records if not r["en"]]
    missing_zh = [r["id"] for r in records if not r["zh"]]
    audit = {
        "schema_version": 1,
        "statistics": {
            "unique_ids": len(records),
            "bilingual": sum(r["status"] == "bilingual" for r in records),
            "csv_union_ids": len(csv_ids),
            "csv_bilingual_ids": len(set(languages["en"]) & set(languages["zh-CN"])),
            "sjson_active_ids": len(sjson_rows),
            "sjson_with_lua_english": sum(bool(lua.get(i)) for i in sjson_rows),
            "csv_sjson_overlap": len(set(csv_ids) & set(sjson_rows)),
            "missing_en": len(missing_en),
            "missing_zh": len(missing_zh),
            "channels": len({r["channel"] for r in records}),
        },
        "sources": {
            "subtitle_csv": csv_files,
            "sjson": [p.relative_to(root).as_posix() for p in sjson_files],
            "lua_file_count": len(lua_files),
            "lua_root": "Content/Scripts",
        },
        "missing": {"en": missing_en, "zh": missing_zh},
        "issue_counts": dict(sorted(Counter(i["kind"] for i in issues).items())),
        "issues": issues,
    }
    return records, audit


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _csv_bytes(records: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode("utf-8")


def _md_escape(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def render_readme(records: list[dict], audit: dict) -> str:
    stats = audit["statistics"]
    grouped = Counter(r["channel"] for r in records)
    lines = ["# Hades 中英台词索引", "", "本目录由 `python -m hades_dialogue extract` 确定性生成。ID 是唯一键；不会按台词文本去重。", "",
             "## 统计", "", f"- 唯一 ID：**{stats['unique_ids']:,}**", f"- 中英非空配对：**{stats['bilingual']:,}**",
             f"- CSV 并集：**{stats['csv_union_ids']:,}**", f"- 当前 SJSON 集合：**{stats['sjson_active_ids']:,}**",
             f"- CSV / SJSON 重叠：**{stats['csv_sjson_overlap']:,}**", "", "## 频道", ""]
    for channel, count in sorted(grouped.items()):
        lines.append(f"- [{channel}](characters/{channel}.md)：{count:,} 条")
    lines += ["", "## 文件", "", "- `all.csv`：便于电子表格和脚本处理", "- `all.json`：完整结构化记录",
              "- `audit.json`：来源、冲突、候选消歧与完整性审计", "", "来源路径全部相对于游戏根目录。", ""]
    return "\n".join(lines)


def render_channel(channel: str, records: list[dict]) -> str:
    lines = [f"# {channel}", "", f"共 {len(records):,} 条。", ""]
    for record in records:
        lines.extend([f"## `{record['id']}`", "", f"**Speaker:** {record['speaker']}", "",
                      "**EN**", "", _md_escape(record["en"]), "", "**中文**", "", _md_escape(record["zh"]), ""])
    return "\n".join(lines)


def extract(game_root: Path, output: Path) -> tuple[list[dict], dict]:
    output = output.expanduser()
    if output.is_symlink():
        raise ValueError(f"refusing symlink output directory: {output}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    characters = output / "characters"
    managed_static = [output / name for name in ("all.csv", "all.json", "audit.json", "README.md")]
    for path in [characters, *managed_static]:
        if path.is_symlink():
            raise ValueError(f"refusing symlink in managed output: {path}")
    characters.mkdir(exist_ok=True)
    for path in characters.iterdir():
        if path.is_symlink():
            raise ValueError(f"refusing symlink in managed output: {path}")

    records, audit = collect(game_root)
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["channel"]].append(record)
    files: dict[Path, bytes] = {
        output / "all.csv": _csv_bytes(records), output / "all.json": _json_bytes(records),
        output / "audit.json": _json_bytes(audit), output / "README.md": render_readme(records, audit).encode("utf-8")}
    for channel, values in sorted(grouped.items()):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", channel)
        path = characters / f"{safe}.md"
        if path.is_symlink():
            raise ValueError(f"refusing symlink in managed output: {path}")
        files[path] = render_channel(channel, values).encode("utf-8")
    for path in sorted(files, key=lambda p: p.as_posix()):
        path.write_bytes(files[path])
    return records, audit
