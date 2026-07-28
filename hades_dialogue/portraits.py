"""Local-only extraction of Hades character portraits from the user's game files."""
from __future__ import annotations

import importlib
import io
import json
import tempfile
from pathlib import Path
from typing import Callable, Iterable

from .audio import _atomic_write, _safe_output_directory

GUI_PACKAGE = Path("Content/Win/Packages/GUI.pkg")
ATLAS_ENTRIES = tuple(f"*GUI_Textures{index}" for index in range(94, 118))

SOURCE_BY_CHARACTER = {
    "Achilles": "Portraits_Achilles_01.png",
    "Alecto": "Portraits_Alecto_01.png",
    "Aphrodite": "Portraits_Aphrodite_01.png",
    "Ares": "Portraits_Ares_01.png",
    "Artemis": "Portraits_Artemis_01.png",
    "Athena": "Portraits_Athena_01.png",
    "Chaos": "Portraits_Chaos_01.png",
    "Charon": "Portraits_Charon_01.png",
    "Demeter": "Portraits_Demeter_01.png",
    "Dionysus": "Portraits_Dionysus_01.png",
    "Dusa": "Portraits_Medusa_01.png",
    "Eurydice": "Portraits_Eurydice_01.png",
    "Hades": "Portraits_Hades_01.png",
    "Hermes": "Portraits_Hermes_01.png",
    "Hypnos": "Portraits_Hypnos_01.png",
    "Megaera": "Portraits_Megaera_01.png",
    "Minotaur": "Portraits_Minotaur_01.png",
    "Nyx": "Portraits_Nyx_01.png",
    "Orpheus": "Portraits_Orpheus_01.png",
    "Patroclus": "Portraits_Patroclus_01.png",
    "Persephone": "Portraits_Persephone_01.png",
    "Poseidon": "Portraits_Poseidon_01.png",
    "Sisyphus": "Portraits_Sisyphus_01.png",
    "Skelly": "Portraits_Skelly_01.png",
    "Thanatos": "Portraits_Thanatos_01.png",
    "Theseus": "Portraits_Theseus_01.png",
    "Tisiphone": "Portraits_Tisiphone_01.png",
    "Zagreus": "Portraits_Zagreus_01.png",
    "Zeus": "Portraits_Zeus_01.png",
}

CHANNEL_ALIASES = {
    "HadesField": "Hades",
    "MegaeraExtra": "Megaera",
    "MegaeraField": "Megaera",
    "MegaeraHome": "Megaera",
    "ThanatosExtra": "Thanatos",
    "ThanatosField": "Thanatos",
    "ZagreusExtra": "Zagreus",
    "ZagreusField": "Zagreus",
    "ZagreusHome": "Zagreus",
    "ZagreusScratch": "Zagreus",
}


def _extract_package(package: Path, target: Path, entries: Iterable[str]) -> None:
    try:
        deppth2 = importlib.import_module("deppth2.deppth2")
    except ImportError as exc:
        raise ValueError(
            "portrait extraction requires deppth2; install it with "
            "`python -m pip install -r requirements-portraits.txt`"
        ) from exc
    deppth2.extract(
        str(package),
        str(target),
        *tuple(entries),
        subtextures=True,
        logger=lambda _message: None,
    )


def _portrait_webp(source: Path) -> bytes:
    try:
        image_module = importlib.import_module("PIL.Image")
    except ImportError as exc:
        raise ValueError("portrait extraction requires Pillow") from exc
    with image_module.open(source) as image:
        image = image.convert("RGBA")
        bounds = image.getbbox()
        if bounds:
            image = image.crop(bounds)
        image.thumbnail((900, 900), image_module.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=90, method=6)
        return output.getvalue()


def extract_portraits(
    game_root: Path,
    output: Path,
    *,
    package_extractor: Callable[[Path, Path, Iterable[str]], None] = _extract_package,
    image_processor: Callable[[Path], bytes] = _portrait_webp,
) -> dict[str, int]:
    """Extract default portraits for dialogue channels into a local web directory."""
    package = game_root.expanduser().resolve() / GUI_PACKAGE
    if not package.is_file():
        raise ValueError(f"Hades GUI package not found: {package}")

    with _safe_output_directory(output) as (output, output_fd):
        exported: dict[str, str] = {}
        with tempfile.TemporaryDirectory(prefix="hades-portraits-") as temporary:
            extracted = Path(temporary)
            package_extractor(package, extracted, ATLAS_ENTRIES)
            portrait_root = extracted / "textures/Portraits"
            for character, filename in SOURCE_BY_CHARACTER.items():
                source = portrait_root / filename
                if not source.is_file():
                    continue
                destination_name = f"{character}.webp"
                destination = output / destination_name
                _atomic_write(destination, image_processor(source), directory_fd=output_fd)
                exported[character] = destination_name

        channel_portraits = dict(exported)
        channel_portraits.update({
            channel: exported[character]
            for channel, character in CHANNEL_ALIASES.items()
            if character in exported
        })
        _atomic_write(
            output / "manifest.json",
            (json.dumps({
                "schemaVersion": 1,
                "count": len(exported),
                "portraits": dict(sorted(channel_portraits.items())),
            }, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            directory_fd=output_fd,
        )
        return {"exported": len(exported), "channels": len(channel_portraits)}
