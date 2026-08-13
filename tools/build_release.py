"""Build and validate the deterministic OddCast release archive."""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ADDON_ROOT = ROOT / "addons" / "oddcast"
PAYLOAD_FILES = (
    "LICENSE-LUASHITACAST-MIT",
    "LICENSE-ODDCAST-GPL-3.0",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "oddcast.lua",
    "weakness_data.lua",
    "weakness_data_manifest.json",
)
ARCHIVE_MEMBERS = tuple(f"oddcast/{name}" for name in PAYLOAD_FILES)
VERSION_PATTERN = re.compile(r"addon\.version\s*=\s*'([0-9]+\.[0-9]+\.[0-9]+)';")
COMMIT_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
REPARSE_POINT = 0x0400
MAX_RELEASE_BYTES = 2 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024


class ReleaseError(RuntimeError):
    """Raised when a release input or artifact violates the package contract."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & REPARSE_POINT
    )


def _source_version(source: bytes | None = None) -> str:
    if source is None:
        source = (ADDON_ROOT / "oddcast.lua").read_bytes()
    try:
        source_text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseError("oddcast.lua must be valid UTF-8") from error
    matches = VERSION_PATTERN.findall(source_text)
    if len(matches) != 1:
        raise ReleaseError("oddcast.lua must declare exactly one semantic version")
    return matches[0]


def _git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ReleaseError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def _source_identity(allow_dirty: bool) -> tuple[str, bool]:
    commit = _git_text("rev-parse", "HEAD")
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise ReleaseError("source commit is not a full Git object ID")
    dirty = bool(_git_text("status", "--porcelain", "--untracked-files=all"))
    if dirty and not allow_dirty:
        raise ReleaseError("official release builds require a clean worktree")
    return commit, dirty


def _same_source_identity(expected: tuple[str, bool], allow_dirty: bool) -> None:
    if _source_identity(allow_dirty) != expected:
        raise ReleaseError("source identity changed while collecting the release payload")


def _assert_safe_new_output(output: Path) -> None:
    root = ROOT.resolve()
    resolved = output.resolve(strict=False)
    internal_release_root = (ROOT / "build" / "release").resolve(strict=False)
    inside_repository = resolved == root or root in resolved.parents
    inside_release_root = (
        resolved == internal_release_root or internal_release_root in resolved.parents
    )
    if inside_repository and not inside_release_root:
        raise ReleaseError("release output inside the repository must use build/release")
    if output.exists() or output.is_symlink():
        raise ReleaseError("release output must not already exist")

    parent = output.parent
    if not parent.exists() and not inside_release_root:
        raise ReleaseError("release output parent must be an existing directory")
    probe = parent
    while not probe.exists():
        if probe.parent == probe:
            raise ReleaseError("release output has no existing parent")
        probe = probe.parent
    if not probe.is_dir():
        raise ReleaseError("release output parent must be a directory")
    while True:
        if _is_link_or_reparse(probe):
            raise ReleaseError("release output cannot traverse a link or reparse point")
        if probe.parent == probe:
            break
        probe = probe.parent


def _payload() -> dict[str, bytes]:
    if not ADDON_ROOT.is_dir() or _is_link_or_reparse(ADDON_ROOT):
        raise ReleaseError("addon distribution root must be a regular directory")

    entries = list(ADDON_ROOT.iterdir())
    for path in entries:
        if _is_link_or_reparse(path) or not path.is_file():
            raise ReleaseError(f"unexpected non-regular payload entry: {path.name}")
    actual = {path.name for path in entries}
    expected = set(PAYLOAD_FILES)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ReleaseError(f"payload allowlist mismatch; missing={missing}, extra={extra}")

    return {
        f"oddcast/{name}": (ADDON_ROOT / name).read_bytes()
        for name in PAYLOAD_FILES
    }


def _write_archive(path: Path, payload: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as package:
        for member in sorted(payload):
            info = zipfile.ZipInfo(member, FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            package.writestr(info, payload[member])


def _manifest_bytes(
    version: str,
    commit: str,
    dirty: bool,
    archive_name: str,
    archive_sha256: str,
    payload: dict[str, bytes],
) -> bytes:
    manifest = {
        "archive": archive_name,
        "archiveSha256": archive_sha256,
        "files": {
            member: {"sha256": _sha256_bytes(value), "size": len(value)}
            for member, value in sorted(payload.items())
        },
        "kind": "oddcast-release",
        "schema": 1,
        "sourceCommit": commit,
        "sourceDirty": dirty,
        "version": version,
    }
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_release(output: Path, expected_version: str, allow_dirty: bool) -> None:
    _assert_safe_new_output(output)
    source_identity = _source_identity(allow_dirty)
    commit, dirty = source_identity
    payload = _payload()
    _same_source_identity(source_identity, allow_dirty)
    version = _source_version(payload["oddcast/oddcast.lua"])
    if version != expected_version:
        raise ReleaseError(
            f"source version {version} does not match expected version {expected_version}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}-stage-", dir=output.parent
    ) as temp:
        staged = Path(temp) / output.name
        staged.mkdir()
        archive = staged / f"OddCast-v{version}.zip"
        _write_archive(archive, payload)
        archive_sha256 = _sha256_file(archive)

        manifest_path = staged / "MANIFEST.json"
        manifest_path.write_bytes(
            _manifest_bytes(
                version,
                commit,
                dirty,
                archive.name,
                archive_sha256,
                payload,
            )
        )
        checksum_path = staged / "SHA256SUMS.txt"
        checksum_path.write_text(
            f"{archive_sha256}  {archive.name}\n"
            f"{_sha256_file(manifest_path)}  {manifest_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        _same_source_identity(source_identity, allow_dirty)
        validate_release(staged, expected_version)
        os.replace(staged, output)


def validate_release(output: Path, expected_version: str) -> None:
    expected_artifacts = {
        f"OddCast-v{expected_version}.zip",
        "MANIFEST.json",
        "SHA256SUMS.txt",
    }
    if not output.is_dir() or _is_link_or_reparse(output):
        raise ReleaseError("release output must be a regular directory")
    entries = list(output.iterdir())
    for path in entries:
        if _is_link_or_reparse(path) or not path.is_file():
            raise ReleaseError(f"unexpected non-regular release artifact: {path.name}")
    if {path.name for path in entries} != expected_artifacts:
        raise ReleaseError("release artifact list does not match the 1.0 contract")

    manifest_path = output / "MANIFEST.json"
    if manifest_path.stat().st_size > MAX_RELEASE_BYTES:
        raise ReleaseError("release manifest exceeds the size limit")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"release manifest is unreadable: {error}") from error
    if not isinstance(manifest, dict):
        raise ReleaseError("release manifest must be an object")
    if manifest.get("schema") != 1 or manifest.get("kind") != "oddcast-release":
        raise ReleaseError("release manifest identity is invalid")
    if manifest.get("version") != expected_version:
        raise ReleaseError("release manifest version does not match the expected version")
    archive_name = f"OddCast-v{expected_version}.zip"
    if manifest.get("archive") != archive_name:
        raise ReleaseError("release manifest archive name is invalid")
    if COMMIT_PATTERN.fullmatch(str(manifest.get("sourceCommit", ""))) is None:
        raise ReleaseError("release manifest source commit is invalid")
    if type(manifest.get("sourceDirty")) is not bool:
        raise ReleaseError("release manifest dirty state is invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(ARCHIVE_MEMBERS):
        raise ReleaseError("release manifest member list is invalid")

    archive = output / archive_name
    if archive.stat().st_size > MAX_RELEASE_BYTES:
        raise ReleaseError("release archive exceeds the size limit")
    archive_sha256 = _sha256_file(archive)
    if manifest.get("archiveSha256") != archive_sha256:
        raise ReleaseError("release archive SHA-256 does not match the manifest")

    try:
        with zipfile.ZipFile(archive) as package:
            infos = package.infolist()
            names = [info.filename for info in infos]
            if names != sorted(ARCHIVE_MEMBERS) or len(names) != len(set(names)):
                raise ReleaseError("release archive member list is invalid")
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_RELEASE_BYTES:
                raise ReleaseError("release payload exceeds the size limit")
            for info in infos:
                member = PurePosixPath(info.filename)
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or member.parts[0] != "oddcast"
                    or info.is_dir()
                ):
                    raise ReleaseError("release archive contains an unsafe member path")
                mode = (info.external_attr >> 16) & 0xFFFF
                if not stat.S_ISREG(mode):
                    raise ReleaseError("release archive contains a non-regular member")
                if info.date_time != FIXED_ZIP_TIME or info.compress_type != zipfile.ZIP_STORED:
                    raise ReleaseError("release archive metadata is not deterministic")
                expected = files[info.filename]
                if (
                    not isinstance(expected, dict)
                    or expected.get("size") != info.file_size
                    or info.file_size > MAX_RELEASE_BYTES
                ):
                    raise ReleaseError(
                        f"release member size does not match the manifest: {info.filename}"
                    )
                digest = hashlib.sha256()
                with package.open(info) as handle:
                    for chunk in iter(lambda: handle.read(READ_CHUNK_BYTES), b""):
                        digest.update(chunk)
                if expected.get("sha256") != digest.hexdigest():
                    raise ReleaseError(
                        f"release member does not match the manifest: {info.filename}"
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseError(f"release archive is unreadable: {error}") from error

    expected_checksums = (
        f"{archive_sha256}  {archive_name}\n"
        f"{_sha256_file(manifest_path)}  MANIFEST.json\n"
    )
    checksum_path = output / "SHA256SUMS.txt"
    if checksum_path.stat().st_size > 1024:
        raise ReleaseError("release checksum file exceeds the size limit")
    try:
        actual_checksums = checksum_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise ReleaseError(f"release checksum file is unreadable: {error}") from error
    if actual_checksums != expected_checksums:
        raise ReleaseError("release checksum file does not match the artifacts")


def check_release(output: Path, expected_version: str, allow_dirty: bool) -> None:
    validate_release(output, expected_version)
    with tempfile.TemporaryDirectory(prefix="oddcast-release-check-") as temp:
        rebuilt = Path(temp) / "release"
        build_release(rebuilt, expected_version, allow_dirty)
        for name in sorted(path.name for path in output.iterdir()):
            if not filecmp.cmp(output / name, rebuilt / name, shallow=False):
                raise ReleaseError(f"release artifact is not reproducible: {name}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow a development artifact whose manifest records sourceDirty=true",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.check:
            check_release(args.output.resolve(), args.expect_version, args.allow_dirty)
        else:
            build_release(args.output.resolve(), args.expect_version, args.allow_dirty)
    except (OSError, ReleaseError, subprocess.SubprocessError) as error:
        print(f"OddCast release error: {error}", file=sys.stderr)
        return 2
    action = "Verified" if args.check else "Built"
    print(f"{action} OddCast v{args.expect_version} release at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
