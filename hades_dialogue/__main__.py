from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audio import extract_audio, make_vgmstream_decoder
from .pipeline import collect, extract
from .portraits import extract_portraits


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m hades_dialogue", description="Extract and audit Hades EN/zh-CN dialogue")
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("extract", "audit", "extract-audio", "extract-portraits"):
        command = commands.add_parser(name)
        command.add_argument("--game-root", required=True, type=Path)
        if name == "extract":
            command.add_argument("--output", required=True, type=Path)
        elif name == "extract-audio":
            command.add_argument("--output", type=Path, default=Path("web/public/audio"))
            command.add_argument("--vgmstream-cli", type=Path)
        elif name == "extract-portraits":
            command.add_argument("--output", type=Path, default=Path("web/public/portraits"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "extract":
            _, audit = extract(args.game_root, args.output)
        elif args.command == "extract-audio":
            records, _ = collect(args.game_root)
            fallback = make_vgmstream_decoder(args.vgmstream_cli) if args.vgmstream_cli else None
            result = extract_audio(
                args.game_root,
                args.output,
                dialogue_ids=(record["id"] for record in records),
                fallback_decoder=fallback,
                progress=lambda done, total, name: print(
                    f"extracting audio {done:,}/{total:,}: {name}", file=sys.stderr, flush=True
                ),
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        elif args.command == "extract-portraits":
            result = extract_portraits(args.game_root, args.output)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        else:
            _, audit = collect(args.game_root)
        print(json.dumps(audit["statistics"], ensure_ascii=False, sort_keys=True))
        return 0 if not audit["missing"]["en"] and not audit["missing"]["zh"] else 2
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
