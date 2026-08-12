#!/usr/bin/env python3
"""Build and validate OddCast's global mob-name static weakness dataset."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Iterable, Sequence


SCHEMA = 2
# AGENT_MIN: reason=OddCast intentionally models ordinary mob-family behavior;
# ceiling=never claim live per-spawn accuracy; upgrade=add a narrow exact-name
# override only after a reported common-family miscast.
POLICY = "global-name-v2:all-active-joined-spawns,typical-profile,lowest-id-tie,no-zero-position,no-invalid-identity,no-missing-join"
ELEMENTS = ("Fire", "Ice", "Wind", "Earth", "Lightning", "Water")
SQL_TABLES = {
    "spawns": ("sql/mob_spawn_points.sql", "mob_spawn_points"),
    "groups": ("sql/mob_groups.sql", "mob_groups"),
    "pools": ("sql/mob_pools.sql", "mob_pools"),
    "resists": ("sql/mob_resistances.sql", "mob_resistances"),
    "families": ("sql/mob_species_system.sql", "mob_family_system"),
}
SEMANTIC_SOURCE_FILES = (
    "scripts/enum/magic.lua",
    "scripts/enum/mod.lua",
    "scripts/globals/combat/damage_multipliers.lua",
    "scripts/globals/combat/magic_hit_rate.lua",
    "scripts/globals/spells/damage_spell.lua",
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DataError(RuntimeError):
    """Raised when source or generated weakness data is not trustworthy."""


def _split_tuples(values_text: str) -> Iterable[str]:
    quoted = False
    depth = 0
    start = 0
    index = 0
    while index < len(values_text):
        char = values_text[index]
        if char == "'" and (index == 0 or values_text[index - 1] != "\\"):
            if quoted and index + 1 < len(values_text) and values_text[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == "(":
                if depth == 0:
                    start = index + 1
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    raise DataError("unbalanced SQL tuple")
                if depth == 0:
                    yield values_text[start:index]
        index += 1
    if quoted or depth != 0:
        raise DataError("unterminated SQL tuple")


def _split_fields(tuple_text: str) -> tuple[str, ...]:
    fields: list[str] = []
    quoted = False
    start = 0
    index = 0
    while index < len(tuple_text):
        char = tuple_text[index]
        if char == "'" and (index == 0 or tuple_text[index - 1] != "\\"):
            if quoted and index + 1 < len(tuple_text) and tuple_text[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif char == "," and not quoted:
            fields.append(tuple_text[start:index].strip())
            start = index + 1
        index += 1
    if quoted:
        raise DataError("unterminated SQL string")
    fields.append(tuple_text[start:].strip())
    return tuple(fields)


def _parse_atom(value: str) -> object | None:
    value = value.strip()
    if value.upper() == "NULL":
        return None
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return (
            value[1:-1]
            .replace("''", "'")
            .replace("\\'", "'")
            .replace("\\\\", "\\")
        )
    try:
        return int(value, 0)
    except ValueError:
        try:
            parsed = float(value)
        except ValueError as error:
            numeric_expression = re.fullmatch(
                r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[+-](?:\d+(?:\.\d*)?|\.\d+))+",
                value,
            )
            if numeric_expression is None:
                raise DataError(f"unsupported SQL atom: {value}") from error
            try:
                terms = re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value)
                parsed = float(sum((Decimal(term) for term in terms), Decimal(0)))
            except (InvalidOperation, ValueError) as expression_error:
                raise DataError(f"unsupported SQL atom: {value}") from expression_error
        if not math.isfinite(parsed):
            raise DataError(f"non-finite SQL atom: {value}")
        return parsed


def read_insert_rows(path: Path, table: str) -> tuple[tuple[object | None, ...], ...]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError as error:
        raise DataError(f"cannot read source table: {path}") from error
    # CatsEye keeps many historical spawn INSERTs as whole-line SQL comments.
    # They are documentation, not active rows, and must never enter the runtime map.
    text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )
    pattern = re.compile(
        rf"INSERT\s+INTO\s+`?{re.escape(table)}`?\s+VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    rows = [
        tuple(_parse_atom(field) for field in _split_fields(tuple_text))
        for match in pattern.finditer(text)
        for tuple_text in _split_tuples(match.group(1))
    ]
    if not rows:
        raise DataError(f"source table has no INSERT rows: {table}")
    return tuple(rows)


def _integer(value: object | None, label: str) -> int:
    if isinstance(value, bool):
        raise DataError(f"{label} is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise DataError(f"{label} is not an integer: {value!r}")


def _number(value: object | None, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"{label} is not numeric: {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise DataError(f"{label} is not finite")
    return result


def _text(value: object | None, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DataError(f"{label} is blank or not text")
    return value


def normalize_name(value: str) -> str:
    """Return the shared, locale-independent lookup form used by OddCast."""
    return " ".join(value.casefold().replace("_", " ").split())


def _typical_profiles(
    votes: dict[str, Counter[int]],
) -> tuple[dict[str, int], dict[str, int]]:
    selected: dict[str, int] = {}
    ambiguous = 0
    ties = 0
    for key in sorted(votes):
        counts = votes[key]
        if len(counts) > 1:
            ambiguous += 1
        highest = max(counts.values())
        winners = [profile_id for profile_id, count in counts.items() if count == highest]
        if len(winners) > 1:
            ties += 1
        selected[key] = min(winners)
    return selected, {"ambiguous": ambiguous, "ties": ties}


def _unique_map(rows: Sequence[Sequence[object | None]], key_fn, value_fn, label: str):
    output = {}
    for row in rows:
        key = key_fn(row)
        if key in output:
            raise DataError(f"duplicate {label}: {key!r}")
        output[key] = value_fn(row)
    return output


def _source_paths(server_root: Path) -> tuple[Path, ...]:
    sql_paths = tuple(server_root / relative for relative, _ in SQL_TABLES.values())
    semantic_paths = tuple(server_root / relative for relative in SEMANTIC_SOURCE_FILES)
    for path in sql_paths + semantic_paths:
        if not path.is_file():
            raise DataError(f"required source file is missing: {path}")
    return sql_paths + semantic_paths


def source_identity(server_root: Path) -> tuple[str, tuple[Path, ...]]:
    paths = _source_paths(server_root)
    digest = hashlib.sha256()
    digest.update((POLICY + "\n").encode("utf-8"))
    for path in paths:
        relative = path.relative_to(server_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest(), paths


def _git_source_commit(server_root: Path, *, require_clean: bool) -> str:
    commit = subprocess.run(
        ["git", "-C", str(server_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = commit.stdout.strip().lower()
    if commit.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise DataError("CatsEye source commit is unavailable")
    if require_clean:
        material = (
            [relative for relative, _ in SQL_TABLES.values()]
            + list(SEMANTIC_SOURCE_FILES)
        )
        status = subprocess.run(
            ["git", "-C", str(server_root), "status", "--porcelain", "--", *material],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if status.returncode != 0 or status.stdout.strip():
            raise DataError("material CatsEye source paths are dirty")
    return value


def build_model(server_root: Path) -> dict[str, object]:
    rows = {
        name: read_insert_rows(server_root / relative, table)
        for name, (relative, table) in SQL_TABLES.items()
    }
    groups = _unique_map(
        rows["groups"],
        lambda row: (_integer(row[2], "group zone"), _integer(row[0], "group id")),
        lambda row: _integer(row[1], "group pool"),
        "zone/group",
    )
    pools = _unique_map(
        rows["pools"],
        lambda row: _integer(row[0], "pool id"),
        lambda row: (
            _text(row[2], "pool packet name"),
            _integer(row[3], "species id"),
            _integer(row[25], "resistance id"),
        ),
        "pool id",
    )
    families = _unique_map(
        rows["families"],
        lambda row: _integer(row[0], "family species id"),
        lambda row: (
            _text(row[1], "family name"),
            _text(row[3], "superfamily name"),
        ),
        "family species id",
    )
    resists = _unique_map(
        rows["resists"],
        lambda row: _integer(row[0], "resistance id"),
        lambda row: tuple(
            _integer(row[index], "resistance value")
            for index in (*range(7, 13), *range(15, 21))
        ),
        "resistance id",
    )
    for profile_id, profile in resists.items():
        if any(rank < -3 or rank > 11 for rank in profile[6:]):
            raise DataError(f"resistance profile {profile_id} has an out-of-range rank")
    name_votes: dict[str, Counter[int]] = {}
    family_votes: dict[str, Counter[int]] = {}
    included_targets = 0
    excluded: dict[str, int] = {}

    def reject(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    for row in rows["spawns"]:
        if len(row) < 11:
            raise DataError("spawn row has too few columns")
        mob_id = _integer(row[0], "mob id")
        zone = (mob_id >> 12) & 0xFFF
        target_index = mob_id & 0xFFF
        if zone <= 0 or target_index <= 0:
            reject("invalid-identity")
            continue
        if all(_number(row[index], "spawn position") == 0 for index in (7, 8, 9)):
            reject("zero-position")
            continue
        group_id = _integer(row[4], "spawn group")
        pool_id = groups.get((zone, group_id))
        pool = pools.get(pool_id) if pool_id is not None else None
        if pool is None:
            reject("missing-join")
            continue
        packet_name, species_id, resist_id = pool
        profile = resists.get(resist_id)
        if profile is None:
            reject("missing-join")
            continue
        display_name = _text(row[3], "mob display name")
        normalized_names = {normalize_name(display_name), normalize_name(packet_name)}
        for name in normalized_names:
            name_votes.setdefault(name, Counter())[resist_id] += 1
        family = families.get(species_id)
        if family is not None:
            for prefix in {normalize_name(family[0]), normalize_name(family[1])}:
                family_votes.setdefault(prefix, Counter())[resist_id] += 1
        included_targets += 1

    if not name_votes:
        raise DataError("source policy produced no global mob-name records")
    names, name_ambiguity = _typical_profiles(name_votes)
    family_prefixes, family_ambiguity = _typical_profiles(family_votes)
    used_profiles = set(names.values()) | set(family_prefixes.values())
    return {
        "profiles": {profile_id: resists[profile_id] for profile_id in sorted(used_profiles)},
        "names": names,
        "familyPrefixes": family_prefixes,
        "ambiguityCounts": {
            "name": name_ambiguity["ambiguous"],
            "nameTie": name_ambiguity["ties"],
            "familyPrefix": family_ambiguity["ambiguous"],
            "familyPrefixTie": family_ambiguity["ties"],
        },
        "includedTargets": included_targets,
        "excluded": dict(sorted(excluded.items())),
        "sourceRows": len(rows["spawns"]),
    }


def _lua_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "\\r").replace("\n", "\\n") + "'"


def _header(source_commit: str, source_sha256: str) -> list[str]:
    return [
        "-- SPDX-License-Identifier: GPL-3.0-or-later",
        "-- Generated by tools/build_weakness_data.py; do not edit.",
        f"-- CatsEye source commit: {source_commit}",
        f"-- Material input identity: {source_sha256}",
    ]


def render_artifacts(server_root: Path, *, require_clean: bool = True) -> tuple[dict[str, bytes], dict[str, object]]:
    source_sha256, source_paths = source_identity(server_root)
    source_commit = _git_source_commit(server_root, require_clean=require_clean)
    model = build_model(server_root)
    lines = _header(source_commit, source_sha256) + [
        "return {",
        f"  schema={SCHEMA},",
        f"  sourceSha256={_lua_string(source_sha256)},",
        "  elements={'Fire','Ice','Wind','Earth','Lightning','Water'},",
        "  profiles={",
    ]
    profiles = model["profiles"]
    assert isinstance(profiles, dict)
    for profile_id, profile in profiles.items():
        lines.append(f"    [{profile_id}]={{{','.join(str(value) for value in profile)}}},")
    lines.extend(("  },", "  names={"))
    names = model["names"]
    assert isinstance(names, dict)
    for name, profile_id in names.items():
        lines.append(f"    [{_lua_string(name)}]={profile_id},")
    lines.extend(("  },", "  familyPrefixes={"))
    family_prefixes = model["familyPrefixes"]
    assert isinstance(family_prefixes, dict)
    for prefix, profile_id in family_prefixes.items():
        lines.append(f"    [{_lua_string(prefix)}]={profile_id},")
    lines.extend(("  },", "}", ""))
    index_bytes = "\n".join(lines).encode("utf-8")
    artifacts = {"weakness_data.lua": index_bytes}
    file_rows = [
        {
            "path": path,
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            "count": None,
        }
        for path, data in sorted(artifacts.items())
    ]
    manifest = {
        "schema": SCHEMA,
        "kind": "oddcast-static-weakness-data",
        "policy": POLICY,
        "sourceCommit": source_commit,
        "sourceSha256": source_sha256,
        "generatorSha256": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dataLicense": "GPL-3.0-or-later",
        "materialInputCount": len(source_paths),
        "sourceSpawnCount": model["sourceRows"],
        "includedTargetCount": model["includedTargets"],
        "nameCount": len(names),
        "familyPrefixCount": len(family_prefixes),
        "profileCount": len(profiles),
        "ambiguityCounts": model["ambiguityCounts"],
        "excluded": model["excluded"],
        "files": file_rows,
    }
    artifacts["weakness_data_manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return artifacts, manifest


def _generated_inventory(output_root: Path) -> set[str]:
    inventory = {
        name for name in ("weakness_data.lua", "weakness_data_manifest.json")
        if (output_root / name).is_file()
    }
    data_root = output_root / "weakness_data"
    if data_root.is_dir():
        inventory.update(
            path.relative_to(output_root).as_posix()
            for path in data_root.glob("*.lua")
        )
    return inventory


def write_artifacts(output_root: Path, artifacts: dict[str, bytes]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    expected = set(artifacts)
    for stale in sorted(_generated_inventory(output_root) - expected):
        (output_root / stale).unlink()
    for relative, data in artifacts.items():
        path = output_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def check_artifacts(output_root: Path, artifacts: dict[str, bytes]) -> None:
    expected = set(artifacts)
    actual = _generated_inventory(output_root)
    if actual != expected:
        raise DataError(f"generated inventory mismatch: missing={sorted(expected-actual)} unexpected={sorted(actual-expected)}")
    for relative, data in artifacts.items():
        if (output_root / relative).read_bytes() != data:
            raise DataError(f"generated artifact drift: {relative}")


def validate_output(output_root: Path, *, luajit: str | None = None) -> dict[str, object]:
    manifest_path = output_root / "weakness_data_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError("weakness data manifest is missing or invalid") from error
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("kind") != "oddcast-static-weakness-data"
        or manifest.get("policy") != POLICY
        or not isinstance(manifest.get("sourceCommit"), str)
        or re.fullmatch(r"[0-9a-f]{40}", manifest["sourceCommit"]) is None
        or not isinstance(manifest.get("sourceSha256"), str)
        or SHA256_RE.fullmatch(manifest["sourceSha256"]) is None
        or manifest.get("dataLicense") != "GPL-3.0-or-later"
        or manifest.get("generatorSha256")
        != "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or not isinstance(manifest.get("files"), list)
    ):
        raise DataError("weakness data manifest contract is invalid")
    numeric_counts = (
        "materialInputCount",
        "sourceSpawnCount",
        "includedTargetCount",
        "profileCount",
        "nameCount",
        "familyPrefixCount",
    )
    if any(
        not isinstance(manifest.get(key), int) or manifest[key] <= 0
        for key in numeric_counts
    ) or not isinstance(manifest.get("excluded"), dict):
        raise DataError("weakness data manifest counts are invalid")
    if any(not isinstance(value, int) or value < 0 for value in manifest["excluded"].values()):
        raise DataError("weakness data exclusion counts are invalid")
    if manifest["includedTargetCount"] + sum(manifest["excluded"].values()) != manifest["sourceSpawnCount"]:
        raise DataError("weakness data source partition is incomplete")
    expected: set[str] = {"weakness_data_manifest.json"}
    compiled: list[Path] = []
    file_rows: dict[str, dict[str, object]] = {}
    for row in manifest["files"]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise DataError("weakness data manifest file row is invalid")
        relative = row["path"]
        if relative == "weakness_data.lua":
            pass
        else:
            raise DataError(f"unsafe weakness data path: {relative}")
        if relative in expected:
            raise DataError(f"duplicate weakness data path: {relative}")
        expected.add(relative)
        file_rows[relative] = row
        path = output_root / relative
        if not path.is_file():
            raise DataError(f"weakness data file is missing: {relative}")
        actual_sha = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if not SHA256_RE.fullmatch(row["sha256"]) or actual_sha != row["sha256"]:
            raise DataError(f"weakness data hash mismatch: {relative}")
        text = path.read_text(encoding="utf-8")
        if (
            f"-- CatsEye source commit: {manifest['sourceCommit']}" not in text
            or f"sourceSha256='{manifest['sourceSha256']}'" not in text
            or not text.startswith("-- SPDX-License-Identifier: GPL-3.0-or-later\n")
        ):
            raise DataError(f"weakness data source identity mismatch: {relative}")
        compiled.append(path)
    if "weakness_data.lua" not in file_rows:
        raise DataError("weakness data index is not inventoried")
    index_text = (output_root / "weakness_data.lua").read_text(encoding="utf-8")
    if "  elements={'Fire','Ice','Wind','Earth','Lightning','Water'},\n" not in index_text:
        raise DataError("weakness data index element order is invalid")
    try:
        profile_block = index_text.split("  profiles={\n", 1)[1].split("  },\n  names={\n", 1)[0]
        name_block = index_text.split("  names={\n", 1)[1].split("  },\n  familyPrefixes={\n", 1)[0]
        family_block = index_text.split("  familyPrefixes={\n", 1)[1].split("  },\n}", 1)[0]
    except IndexError as error:
        raise DataError("weakness data index structure is invalid") from error
    profile_count = len(re.findall(r"^    \[[0-9]+\]=\{", profile_block, re.MULTILINE))
    if profile_count != manifest["profileCount"]:
        raise DataError("weakness data profile count mismatch")
    if len(re.findall(r"^    \['(?:[^'\\]|\\.)+'\]=[0-9]+,$", name_block, re.MULTILINE)) != manifest["nameCount"]:
        raise DataError("weakness data name count mismatch")
    if len(re.findall(r"^    \['(?:[^'\\]|\\.)+'\]=[0-9]+,$", family_block, re.MULTILINE)) != manifest["familyPrefixCount"]:
        raise DataError("weakness data family-prefix count mismatch")
    ambiguity = manifest.get("ambiguityCounts")
    if not isinstance(ambiguity, dict) or set(ambiguity) != {"name", "nameTie", "familyPrefix", "familyPrefixTie"} or any(not isinstance(value, int) or value < 0 for value in ambiguity.values()):
        raise DataError("weakness data ambiguity counts are invalid")
    if len(manifest["files"]) != 1:
        raise DataError("weakness data file count mismatch")
    actual = _generated_inventory(output_root)
    if actual != expected:
        raise DataError(f"weakness data inventory mismatch: missing={sorted(expected-actual)} unexpected={sorted(actual-expected)}")
    if luajit:
        executable = Path(luajit).resolve()
        if not executable.is_file():
            raise DataError(f"LuaJIT executable is missing: {executable}")
        with tempfile.TemporaryDirectory(prefix="oddcast-luajit-") as temporary:
            for index, path in enumerate(compiled):
                result = subprocess.run(
                    [str(executable), "-b", str(path), str(Path(temporary) / f"{index}.luac")],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    raise DataError(f"LuaJIT rejected {path.name}: {result.stderr.strip()}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-root", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "addons" / "oddcast",
    )
    parser.add_argument("--check", action="store_true", help="compare output with current source")
    parser.add_argument("--validate-output", action="store_true", help="validate checked-in output without source")
    parser.add_argument("--allow-dirty-source", action="store_true")
    parser.add_argument("--luajit", help="also byte-compile every generated Lua file")
    args = parser.parse_args()
    try:
        if args.validate_output:
            manifest = validate_output(args.output_root.resolve(), luajit=args.luajit)
        else:
            if args.server_root is None:
                raise DataError("--server-root is required unless --validate-output is used")
            artifacts, manifest = render_artifacts(
                args.server_root.resolve(), require_clean=not args.allow_dirty_source
            )
            if args.check:
                check_artifacts(args.output_root.resolve(), artifacts)
            else:
                write_artifacts(args.output_root.resolve(), artifacts)
                validate_output(args.output_root.resolve(), luajit=args.luajit)
        print(json.dumps({
            "status": "passed",
            "sourceCommit": manifest["sourceCommit"],
            "sourceSha256": manifest["sourceSha256"],
            "includedTargetCount": manifest["includedTargetCount"],
            "profileCount": manifest["profileCount"],
            "nameCount": manifest["nameCount"],
            "familyPrefixCount": manifest["familyPrefixCount"],
            "ambiguityCounts": manifest["ambiguityCounts"],
            "excluded": manifest["excluded"],
        }, sort_keys=True))
        return 0
    except (DataError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
