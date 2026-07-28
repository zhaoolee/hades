"""Deprecated compatibility entry point; use ``python -m hades_dialogue``."""
from hades_dialogue.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
