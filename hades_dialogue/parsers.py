"""Parsers for Hades subtitle CSV, localized SJSON, and Lua dialogue data."""
from __future__ import annotations

import bisect
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ID_PATTERN = r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+"
_STRING = r'"(?:\\.|[^"\\])*"'


@dataclass(frozen=True)
class TextEntry:
    id: str
    text: str
    source: str
    speaker: str = ""
    comment: str = ""
    channel: str = ""


@dataclass(frozen=True)
class LuaCandidate:
    id: str
    text: str
    source: str
    offset: int
    fallback: bool = False


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _decode(value: str) -> str:
    try:
        return json.loads(value)
    except (ValueError, json.JSONDecodeError):
        # Lua accepts a few escapes JSON does not. Preserve their intended character.
        body = value[1:-1]
        return re.sub(r"\\(.)", lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m.group(1), m.group(1)), body)


def clean_text(value: str) -> str:
    value = value.replace("{!Icons.Music}", "")
    value = re.sub(r"\{#[^}]*\}", "", value)
    value = re.sub(r"<([^>]*)>", r"\1", value)
    return value.strip()


def parse_subtitle_csv(path: Path, language: str, game_root: Path) -> tuple[dict[str, TextEntry], list[dict]]:
    """Read physical columns 4 (ID) and 8 (Line), retaining IDs rather than deduplicating text."""
    result: dict[str, TextEntry] = {}
    issues: list[dict] = []
    source = _relative(path, game_root)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row_number, row in enumerate(reader, 2):
            if len(row) < 8:
                if any(cell.strip() for cell in row):
                    issues.append({"kind": "csv_short_row", "source": source, "row": row_number})
                continue
            dialogue_id, text = row[3].strip(), clean_text(row[7])
            if not dialogue_id or not text:
                continue
            if not re.fullmatch(ID_PATTERN, dialogue_id):
                issues.append({"kind": "invalid_id", "source": source, "row": row_number, "id": dialogue_id})
                continue
            entry = TextEntry(dialogue_id, text, source, channel=path.stem)
            previous = result.get(dialogue_id)
            if previous and previous.text != text:
                issues.append({"kind": "csv_conflict", "language": language, "id": dialogue_id,
                               "source": source, "row": row_number,
                               "kept": previous.text, "discarded": text})
            elif previous:
                issues.append({"kind": "csv_duplicate", "language": language, "id": dialogue_id,
                               "source": source, "row": row_number})
            else:
                result[dialogue_id] = entry
    return result, issues


def _mask(text: str, *, hide_block_comments: bool = True) -> tuple[str, list[tuple[int, int, str]]]:
    """Blank strings/comments while retaining offsets; return discovered comments."""
    chars = list(text)
    comments: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            for k in range(i + 1, min(j - 1, n)):
                chars[k] = " "
            i = j
        elif text.startswith("--[[", i):
            j = text.find("]]", i + 4)
            j = n if j < 0 else j + 2
            comments.append((i, j, text[i + 4:j - 2]))
            if hide_block_comments:
                for k in range(i, j):
                    chars[k] = "\n" if text[k] == "\n" else " "
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            comments.append((i, j, text[i + 2:j - 2]))
            if hide_block_comments:
                for k in range(i, j):
                    chars[k] = "\n" if text[k] == "\n" else " "
            i = j
        elif text.startswith("--", i):
            j = text.find("\n", i + 2)
            j = n if j < 0 else j
            comments.append((i, j, text[i + 2:j]))
            for k in range(i, j):
                chars[k] = " "
            i = j
        else:
            i += 1
    return "".join(chars), comments


def _brace_spans(mask: str) -> list[tuple[int, int]]:
    stack: list[int] = []
    spans: list[tuple[int, int]] = []
    for i, char in enumerate(mask):
        if char == "{":
            stack.append(i)
        elif char == "}" and stack:
            spans.append((stack.pop(), i + 1))
    return spans


def _smallest_span(spans: list[tuple[int, int]], position: int) -> tuple[int, int] | None:
    enclosing = [span for span in spans if span[0] <= position < span[1]]
    return min(enclosing, key=lambda x: x[1] - x[0]) if enclosing else None


def _enclosing_spans(mask: str, positions: Iterable[int]) -> list[tuple[int, int] | None]:
    """Return the smallest enclosing brace span for every queried position.

    Brace pairing and query lookup are each a single pass over ``mask``.  This
    avoids scanning every brace span for every SJSON ID or Lua cue.
    """
    requested = list(positions)
    if not requested:
        return []

    open_braces: list[int] = []
    ends: dict[int, int] = {}
    for offset, char in enumerate(mask):
        if char == "{":
            open_braces.append(offset)
        elif char == "}" and open_braces:
            ends[open_braces.pop()] = offset + 1

    wanted = {position for position in requested if 0 <= position < len(mask)}
    enclosing: dict[int, tuple[int, int] | None] = {}
    active: list[tuple[int, int]] = []
    for offset in range(len(mask)):
        while active and active[-1][1] <= offset:
            active.pop()
        if offset in ends:
            active.append((offset, ends[offset]))
        if offset in wanted:
            enclosing[offset] = active[-1] if active else None

    return [enclosing.get(position) for position in requested]


def parse_sjson(path: Path, game_root: Path) -> tuple[dict[str, TextEntry], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    mask, comments = _mask(text)
    result: dict[str, TextEntry] = {}
    issues: list[dict] = []
    source = _relative(path, game_root)
    id_re = re.compile(r"\bId\s*=\s*(\"(" + ID_PATTERN + r")\")")
    field_re = lambda name: re.compile(r"\b" + name + r"\s*=\s*(" + _STRING + r")")
    # Ignore IDs occurring in comments by requiring visible assignment syntax.
    matches = [match for match in id_re.finditer(text)
               if mask[match.start():match.end()].strip()]
    spans = _enclosing_spans(mask, (match.start() for match in matches))
    field_matches = {
        name: [match for match in field_re(name).finditer(text)
               if name in mask[match.start():match.end()]]
        for name in ("DisplayName", "Speaker")
    }
    direct_fields: dict[str, defaultdict[tuple[int, int], list[re.Match[str]]]] = {}
    for name, found in field_matches.items():
        by_span: defaultdict[tuple[int, int], list[re.Match[str]]] = defaultdict(list)
        for field, field_span in zip(found, _enclosing_spans(mask, (item.start() for item in found))):
            if field_span:
                by_span[field_span].append(field)
        direct_fields[name] = by_span
    for match, span in zip(matches, spans):
        if not span:
            issues.append({"kind": "sjson_unbalanced_object", "id": match.group(2), "source": source})
            continue
        display_values = direct_fields["DisplayName"].get(span, [])
        speaker_values = direct_fields["Speaker"].get(span, [])
        display = display_values[0] if display_values else None
        speaker = speaker_values[0] if speaker_values else None
        if not display:
            issues.append({"kind": "sjson_missing_display_name", "id": match.group(2), "source": source})
            continue
        comment = "\n".join(body.strip() for start, end, body in comments if span[0] <= start and end <= span[1])
        entry = TextEntry(match.group(2), clean_text(_decode(display.group(1))), source,
                          _decode(speaker.group(1)) if speaker else "", comment,
                          match.group(2).split("_", 1)[0])
        old = result.get(entry.id)
        if old and old.text != entry.text:
            issues.append({"kind": "sjson_conflict", "id": entry.id, "source": source,
                           "kept": old.text, "discarded": entry.text})
        elif not old:
            result[entry.id] = entry
    return result, issues


def _active_lua_candidates(text: str, source: str, base_offset: int = 0, fallback: bool = False) -> list[LuaCandidate]:
    mask, comments = _mask(text)
    cue_re = re.compile(r"\bCue\s*=\s*\"/VO/(" + ID_PATTERN + r")\"")
    text_re = re.compile(r"\bText\s*=\s*(" + _STRING + r")")
    found: list[LuaCandidate] = []
    cues = [cue for cue in cue_re.finditer(text)
            if "Cue" in mask[cue.start():cue.end()]]
    spans = _enclosing_spans(mask, (cue.start() for cue in cues))
    text_matches = [match for match in text_re.finditer(text)
                    if "Text" in mask[match.start():match.end()]]
    text_by_span: defaultdict[tuple[int, int], list[re.Match[str]]] = defaultdict(list)
    text_spans = _enclosing_spans(mask, (match.start() for match in text_matches))
    for assignment, assignment_span in zip(text_matches, text_spans):
        if assignment_span:
            text_by_span[assignment_span].append(assignment)
    comment_starts = [start for start, _, _ in comments]
    for cue, span in zip(cues, spans):
        if not span:
            continue
        assignments = text_by_span.get(span, [])
        value = assignments[0].group(1) if assignments else None
        raw_comment = False
        if value is None:
            # Exporter variants put the transcription in the line comment immediately
            # before/after the cue table. Bisect the sorted comments instead of
            # rescanning every comment for every Cue (AudioData has thousands).
            insertion = bisect.bisect_left(comment_starts, span[0])
            nearby: list[str] = []
            if insertion:
                start, end, body = comments[insertion - 1]
                if end <= span[0] and not text[end:span[0]].strip():
                    nearby.append(body)
            after = bisect.bisect_left(comment_starts, span[1])
            if after < len(comments):
                start, _, body = comments[after]
                gap = text[span[1]:start]
                if re.fullmatch(r"[\s,]*", gap) and "\n" not in gap:
                    nearby.append(body)
            for body in nearby:
                m = text_re.search(body)
                if m:
                    value = m.group(1)
                    break
                candidate_text = body.strip()
                if candidate_text:
                    value = candidate_text
                    raw_comment = True
                    break
        if value is not None:
            decoded = value if raw_comment else _decode(value)
            found.append(LuaCandidate(cue.group(1), clean_text(decoded), source,
                                      base_offset + cue.start(), fallback))
    return found


def parse_lua_candidates(paths: Iterable[Path], game_root: Path) -> dict[str, list[LuaCandidate]]:
    result: defaultdict[str, list[LuaCandidate]] = defaultdict(list)
    for path in sorted(paths, key=lambda p: p.as_posix()):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        source = _relative(path, game_root)
        active = _active_lua_candidates(text, source)
        for candidate in active:
            result[candidate.id].append(candidate)
        active_ids = {candidate.id for candidate in active}
        _, comments = _mask(text)
        # Controlled recovery: structured Cue+Text only, and only when no active
        # candidate with that ID exists in this file.
        for start, _, body in comments:
            if not text.startswith("--[[", start):
                continue
            if "/VO/" not in body or "Cue" not in body or "Text" not in body:
                continue
            for candidate in _active_lua_candidates(body, source, start, True):
                if candidate.id not in active_ids:
                    result[candidate.id].append(candidate)
    for values in result.values():
        values.sort(key=lambda c: (c.fallback, c.source, c.offset, c.text))
    return dict(result)
