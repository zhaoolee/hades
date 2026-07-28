from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import collect, extract


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m hades_dialogue", description="Extract and audit Hades EN/zh-CN dialogue")
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("extract", "audit"):
        command = commands.add_parser(name)
        command.add_argument("--game-root", required=True, type=Path)
        if name == "extract":
            command.add_argument("--output", required=True, type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "extract":
            _, audit = extract(args.game_root, args.output)
        else:
            _, audit = collect(args.game_root)
        print(json.dumps(audit["statistics"], ensure_ascii=False, sort_keys=True))
        return 0 if not audit["missing"]["en"] and not audit["missing"]["zh"] else 2
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
