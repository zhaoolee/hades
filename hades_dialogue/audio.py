"""Local-only extraction of Hades voice lines from the user's own game files."""
from __future__ import annotations

import json
import importlib
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable

AUDIO_BANK = Path("Content/Audio/FMOD/Build/Desktop/VO.fsb")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _load_fsb(data: bytes) -> Any:
    try:
        fsb5 = importlib.import_module("fsb5")
    except ImportError as exc:
        raise ValueError(
            "audio extraction requires fsb5; install it with "
            "`python -m pip install -r requirements-audio.txt`"
        ) from exc
    return fsb5.FSB5(data)


def make_vgmstream_decoder(
    executable: str | Path = "vgmstream-cli",
    ffmpeg: str | Path = "ffmpeg",
    timeout: float = 120.0,
) -> Callable[[int, Path], bytes]:
    """Build a decoder for FSB Vorbis variants unsupported by fsb5 1.0."""
    cli = shutil.which(str(executable)) or (str(Path(executable).resolve()) if Path(executable).is_file() else None)
    converter = shutil.which(str(ffmpeg)) or (str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else None)
    if not cli:
        raise ValueError(f"vgmstream-cli not found: {executable}")
    if not converter:
        raise ValueError(f"ffmpeg not found: {ffmpeg}")

    def decode(index: int, source: Path) -> bytes:
        with tempfile.TemporaryFile() as decoder_errors:
            vgmstream = subprocess.Popen(
                [cli, "-i", "-s", str(index), "-p", str(source)],
                stdout=subprocess.PIPE,
                stderr=decoder_errors,
            )
            assert vgmstream.stdout is not None
            try:
                converted = subprocess.run(
                    [converter, "-v", "error", "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", "4", "-f", "ogg", "pipe:1"],
                    stdin=vgmstream.stdout,
                    capture_output=True,
                    timeout=timeout,
                )
                vgmstream.stdout.close()
                try:
                    status = vgmstream.wait(timeout=10)
                except subprocess.TimeoutExpired as exc:
                    vgmstream.kill()
                    vgmstream.wait()
                    raise ValueError(f"vgmstream fallback timed out for subsong {index}") from exc
            except subprocess.TimeoutExpired as exc:
                vgmstream.stdout.close()
                vgmstream.kill()
                vgmstream.wait()
                raise ValueError(f"vgmstream fallback timed out for subsong {index}") from exc
            finally:
                if vgmstream.poll() is None:
                    vgmstream.kill()
                    vgmstream.wait()
            decoder_errors.seek(0)
            stderr = decoder_errors.read().decode("utf-8", "replace")
        if status or converted.returncode or not converted.stdout:
            detail = stderr.strip() or converted.stderr.decode("utf-8", "replace").strip()
            raise ValueError(f"vgmstream fallback failed for subsong {index}: {detail}")
        return converted.stdout

    return decode


@contextmanager
def _safe_output_directory(path: Path):
    """Create/open an absolute directory without following any path-component symlink."""
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(absolute.anchor or os.sep, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                os.mkdir(component, mode=0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise ValueError(f"refusing unsafe output path component: {absolute}") from exc
            os.close(descriptor)
            descriptor = next_descriptor
        yield absolute, descriptor
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, data: bytes, *, directory_fd: int | None = None) -> None:
    """Replace an output atomically without following directory or final symlinks."""
    if directory_fd is None:
        if path.is_symlink():
            raise ValueError(f"refusing symlink output: {path}")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if path.is_symlink():
                raise ValueError(f"refusing symlink output: {path}")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return

    name = path.name
    if not name or name in {".", ".."} or Path(name).name != name:
        raise ValueError(f"unsafe output filename: {name}")
    try:
        existing = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(existing.st_mode):
            raise ValueError(f"refusing symlink output: {path}")
    except FileNotFoundError:
        pass

    temporary_name = f".{name}.{secrets.token_hex(12)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary_name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            existing = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(existing.st_mode):
                raise ValueError(f"refusing symlink output: {path}")
        except FileNotFoundError:
            pass
        os.replace(temporary_name, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    finally:
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def extract_audio(
    game_root: Path,
    output: Path,
    *,
    dialogue_ids: Iterable[str],
    bank_loader: Callable[[bytes], Any] = _load_fsb,
    fallback_decoder: Callable[[int, Path], bytes] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, int | str]:
    """Extract matching VO samples for local playback; never writes outside output."""
    root = game_root.expanduser().resolve()
    bank_path = root / AUDIO_BANK
    if not bank_path.is_file():
        raise ValueError(f"Hades voice bank not found: {bank_path}")

    with _safe_output_directory(output) as (output, output_fd):
        wanted = {value for value in dialogue_ids if _SAFE_ID.fullmatch(value)}
        bank = bank_loader(bank_path.read_bytes())
        extension = bank.get_sample_extension()
        if extension not in {"ogg", "mp3", "wav"}:
            raise ValueError(f"unsupported audio format from FSB bank: {extension}")

        available = {
            sample.name: (index, sample)
            for index, sample in enumerate(bank.samples, 1)
            if _SAFE_ID.fullmatch(sample.name)
        }
        matched = sorted(wanted & available.keys())
        fallback_exported = 0
        for index, dialogue_id in enumerate(matched, 1):
            destination = output / f"{dialogue_id}.{extension}"
            subsong, sample = available[dialogue_id]
            try:
                audio = bank.rebuild_sample(sample)
            except (KeyError, OSError, ValueError):
                if not fallback_decoder:
                    raise
                audio = fallback_decoder(subsong, bank_path)
                fallback_exported += 1
            _atomic_write(destination, audio, directory_fd=output_fd)
            if progress and (index == 1 or index % 250 == 0 or index == len(matched)):
                progress(index, len(matched), dialogue_id)

        manifest = {
            "schemaVersion": 1,
            "extension": extension,
            "count": len(matched),
            "ids": matched,
        }
        _atomic_write(
            output / "manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            directory_fd=output_fd,
        )
        return {
            "bank_samples": len(bank.samples),
            "requested": len(wanted),
            "exported": len(matched),
            "missing": len(wanted - available.keys()),
            "fallback_exported": fallback_exported,
            "extension": extension,
        }
