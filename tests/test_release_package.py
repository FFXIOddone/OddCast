from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "tools" / "build_release.py"
EXPECTED_MEMBERS = {
    "oddcast/LICENSE-LUASHITACAST-MIT",
    "oddcast/LICENSE-ODDCAST-GPL-3.0",
    "oddcast/README.md",
    "oddcast/THIRD_PARTY_NOTICES.md",
    "oddcast/locales.lua",
    "oddcast/oddcast.lua",
    "oddcast/weakness_data.lua",
    "oddcast/weakness_data_manifest.json",
}


def _load_builder():
    spec = importlib.util.spec_from_file_location("oddcast_build_release", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_builder(output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(BUILDER_PATH),
            "--expect-version",
            "1.3.0",
            "--output",
            str(output),
            "--allow-dirty",
            *extra,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_release_builder_is_deterministic_complete_and_version_bound(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for output in (first, second):
        completed = _run_builder(output)
        assert completed.returncode == 0, completed.stdout + completed.stderr

    artifact_names = {
        "MANIFEST.json",
        "OddCast-v1.3.0.zip",
        "SHA256SUMS.txt",
    }
    assert {path.name for path in first.iterdir()} == artifact_names
    assert {path.name for path in second.iterdir()} == artifact_names
    for name in artifact_names:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name

    archive = first / "OddCast-v1.3.0.zip"
    manifest = json.loads((first / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    assert manifest["kind"] == "oddcast-release"
    assert manifest["version"] == "1.3.0"
    assert manifest["archive"] == archive.name
    assert manifest["archiveSha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert set(manifest["files"]) == EXPECTED_MEMBERS
    assert manifest["sourceCommit"]

    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        assert [info.filename for info in infos] == sorted(EXPECTED_MEMBERS)
        assert len(infos) == len({info.filename for info in infos})
        for info in infos:
            payload = package.read(info.filename)
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED
            assert manifest["files"][info.filename] == {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }

    checksums = (first / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    assert checksums == [
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}",
        f"{hashlib.sha256((first / 'MANIFEST.json').read_bytes()).hexdigest()}  MANIFEST.json",
    ]

    check = _run_builder(first, "--check")
    assert check.returncode == 0, check.stdout + check.stderr

    mismatch = subprocess.run(
        [
            sys.executable,
            str(BUILDER_PATH),
            "--expect-version",
            "9.9.9",
            "--output",
            str(tmp_path / "mismatch"),
            "--allow-dirty",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert mismatch.returncode != 0
    assert "expected version 9.9.9" in mismatch.stderr


def test_release_validator_rejects_archive_and_manifest_tampering(
    tmp_path: Path,
) -> None:
    builder = _load_builder()

    archive_tamper = tmp_path / "archive-tamper"
    completed = _run_builder(archive_tamper)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    archive = archive_tamper / "OddCast-v1.3.0.zip"
    archive.write_bytes(archive.read_bytes() + b"tampered")
    with pytest.raises(builder.ReleaseError, match="archive SHA-256"):
        builder.validate_release(archive_tamper, "1.3.0")

    manifest_tamper = tmp_path / "manifest-tamper"
    completed = _run_builder(manifest_tamper)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    manifest_path = manifest_tamper / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].pop("oddcast/THIRD_PARTY_NOTICES.md")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(builder.ReleaseError, match="manifest member list"):
        builder.validate_release(manifest_tamper, "1.3.0")

    consistent_tamper = tmp_path / "consistent-tamper"
    completed = _run_builder(consistent_tamper)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    archive = consistent_tamper / "OddCast-v1.3.0.zip"
    with zipfile.ZipFile(archive) as package:
        payload = {info.filename: package.read(info) for info in package.infolist()}
    readme_name = "oddcast/README.md"
    payload[readme_name] += b"\nTampered after build.\n"
    builder._write_archive(archive, payload)
    manifest_path = consistent_tamper / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archiveSha256"] = builder._sha256_file(archive)
    manifest["files"][readme_name] = {
        "sha256": hashlib.sha256(payload[readme_name]).hexdigest(),
        "size": len(payload[readme_name]),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (consistent_tamper / "SHA256SUMS.txt").write_text(
        f"{builder._sha256_file(archive)}  {archive.name}\n"
        f"{builder._sha256_file(manifest_path)}  MANIFEST.json\n",
        encoding="ascii",
        newline="\n",
    )
    builder.validate_release(consistent_tamper, "1.3.0")
    with pytest.raises(builder.ReleaseError, match="not reproducible"):
        builder.check_release(consistent_tamper, "1.3.0", True)


def test_release_builder_refuses_existing_or_source_outputs_without_writing(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    completed = _run_builder(existing)
    assert completed.returncode != 0
    assert marker.read_text(encoding="utf-8") == "keep"
    assert {path.name for path in existing.iterdir()} == {"keep.txt"}

    unsafe = ROOT / "tools" / "unsafe-release-output"
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER_PATH),
            "--expect-version",
            "1.3.0",
            "--output",
            str(unsafe),
            "--allow-dirty",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode != 0
    assert not unsafe.exists()


def test_release_source_identity_contract_is_exact_and_fail_closed(monkeypatch) -> None:
    builder = _load_builder()
    commit = "a" * 40

    def dirty_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return commit
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return " M addons/oddcast/oddcast.lua"
        raise AssertionError(args)

    monkeypatch.setattr(builder, "_git_text", dirty_git)
    with pytest.raises(builder.ReleaseError, match="clean worktree"):
        builder._source_identity(False)
    assert builder._source_identity(True) == (commit, True)

    monkeypatch.setattr(builder, "_git_text", lambda *args: "b" * 41)
    with pytest.raises(builder.ReleaseError, match="full Git object ID"):
        builder._source_identity(True)


def test_release_version_is_derived_from_the_collected_payload(
    tmp_path: Path, monkeypatch
) -> None:
    builder = _load_builder()
    payload = {member: member.encode("utf-8") for member in builder.ARCHIVE_MEMBERS}
    payload["oddcast/oddcast.lua"] = b"addon.version = '1.3.0';\n"
    source_identity = ("a" * 40, True)
    original_source_version = builder._source_version

    monkeypatch.setattr(builder, "_source_identity", lambda allow_dirty: source_identity)
    monkeypatch.setattr(builder, "_same_source_identity", lambda expected, allow_dirty: None)
    monkeypatch.setattr(builder, "_payload", lambda: payload)

    def version_from_payload(source=None):
        assert source is payload["oddcast/oddcast.lua"]
        return original_source_version(source)

    monkeypatch.setattr(
        builder,
        "_source_version",
        version_from_payload,
    )
    output = tmp_path / "release"
    builder.build_release(output, "1.3.0", True)
    manifest = json.loads((output / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.3.0"
    assert manifest["sourceCommit"] == source_identity[0]
