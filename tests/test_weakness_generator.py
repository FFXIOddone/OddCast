from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tools" / "build_weakness_data.py"
SPEC = importlib.util.spec_from_file_location("oddcast_weakness_generator", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def _write_table(root: Path, relative: str, table: str, rows: list[tuple[object, ...]]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)

    def atom(value: object) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, str):
            return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
        return str(value)

    statements = [
        f"INSERT INTO `{table}` VALUES ({','.join(atom(value) for value in row)});"
        for row in rows
    ]
    path.write_text("\n".join(statements) + "\n", encoding="utf-8", newline="\n")


def _resistance_row(profile_id: int) -> tuple[object, ...]:
    values: list[object] = [profile_id, "Proof"] + [0] * 29
    values[7:13] = [1000, 0, -1000, 0, 500, 0]
    values[15:21] = [-1, 0, 1, 2, 3, 4]
    assert len(values) == 31
    return tuple(values)


def _server_fixture(tmp_path: Path) -> Path:
    server = tmp_path / "server"
    safe_id = (100 << 12) | 321
    zero_id = (100 << 12) | 322
    missing_id = (100 << 12) | 323
    pool_mod_id = (100 << 12) | 324
    species_mod_id = (100 << 12) | 325
    scripted_id = (100 << 12) | 326

    _write_table(
        server,
        "sql/zone_settings.sql",
        "zone_settings",
        [(100, 2, "127.0.0.1", 54230, "Test_Zone", 0, 0, 0, 0, 0, 0.0, 0)],
    )
    _write_table(
        server,
        "sql/mob_groups.sql",
        "mob_groups",
        [
            (1, 10, 100, "Safe", 0, 0, 0, 0, 0, 0, None),
            (2, 20, 100, "PoolMod", 0, 0, 0, 0, 0, 0, None),
            (3, 30, 100, "SpeciesMod", 0, 0, 0, 0, 0, 0, None),
            (4, 40, 100, "Scripted", 0, 0, 0, 0, 0, 0, None),
        ],
    )

    def pool(pool_id: int, species_id: int) -> tuple[object, ...]:
        row: list[object] = [0] * 28
        row[0], row[1], row[2], row[3] = pool_id, f"Pool_{pool_id}", f"Pool {pool_id}", species_id
        row[4] = "0x00"
        row[25] = 1
        return tuple(row)

    _write_table(
        server,
        "sql/mob_pools.sql",
        "mob_pools",
        [pool(10, 1), pool(20, 2), pool(30, 3), pool(40, 4)],
    )
    _write_table(
        server,
        "sql/mob_resistances.sql",
        "mob_resistances",
        [_resistance_row(1)],
    )
    _write_table(
        server,
        "sql/mob_species_system.sql",
        "mob_family_system",
        [
            (1, "Rabbit", 10, "Beast"),
            (2, "Slime", 20, "Amorph"),
            (3, "Bee", 30, "Vermin"),
            (4, "Orc", 40, "Beastman"),
        ],
    )
    _write_table(
        server,
        "sql/mob_pool_mods.sql",
        "mob_pool_mods",
        [(10, 36, 40, 1), (20, 831, 10, 0)],
    )
    _write_table(
        server,
        "sql/mob_species_mods.sql",
        "mob_species_mods",
        [(1, 23, 10, 0), (3, 29, 10, 0)],
    )

    def spawn(mob_id: int, name: str, display: str, group: int, position=(1.0, 2.0, 3.0)):
        return (mob_id, 0, name, display, group, 1, 2, *position, 0)

    _write_table(
        server,
        "sql/mob_spawn_points.sql",
        "mob_spawn_points",
        [
            spawn(safe_id, "Proof_Rabbit", "Proof Rabbit's Echo", 1),
            spawn(zero_id, "Zero", "Zero", 1, (0.0, 0.0, 0.0)),
            spawn(missing_id, "Missing", "Missing", 99),
            spawn(pool_mod_id, "Pool_Mod", "Pool Mod", 2),
            spawn(species_mod_id, "Species_Mod", "Species Mod", 3),
            spawn(scripted_id, "Scripted_Mob", "Scripted Mob", 4),
        ],
    )
    script = server / "scripts" / "zones" / "Test_Zone" / "mobs" / "Scripted_Mob.lua"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("return {}\n", encoding="utf-8", newline="\n")
    for relative in generator.SEMANTIC_SOURCE_FILES:
        semantic = server / relative
        semantic.parent.mkdir(parents=True, exist_ok=True)
        semantic.write_text("return {}\n", encoding="utf-8", newline="\n")
    return server


def test_sql_parser_handles_escaped_apostrophes_and_numeric_positions(tmp_path: Path) -> None:
    path = tmp_path / "source.sql"
    path.write_text(
        "-- INSERT INTO `proof` VALUES (999,'Commented',0,NULL,0);\n"
        "INSERT INTO `proof` VALUES (1,'Orc\\'s Wyvern',-3.125,NULL,-464.527-320);\n",
        encoding="utf-8",
        newline="\n",
    )
    assert generator.read_insert_rows(path, "proof") == (
        (1, "Orc's Wyvern", -3.125, None, -784.527),
    )


def test_model_votes_across_dynamic_rows_and_excludes_only_inactive_or_unjoined(tmp_path: Path) -> None:
    server = _server_fixture(tmp_path)
    model = generator.build_model(server)
    assert model["names"] == {
        "pool 10": 1,
        "pool 20": 1,
        "pool 30": 1,
        "pool 40": 1,
        "pool mod": 1,
        "proof rabbit's echo": 1,
        "scripted mob": 1,
        "species mod": 1,
    }
    assert model["familyPrefixes"] == {
        "amorph": 1,
        "beast": 1,
        "beastman": 1,
        "bee": 1,
        "orc": 1,
        "rabbit": 1,
        "slime": 1,
        "vermin": 1,
    }
    assert model["profiles"] == {
        1: (1000, 0, -1000, 0, 500, 0, -1, 0, 1, 2, 3, 4)
    }
    assert model["includedTargets"] == 4
    assert model["ambiguityCounts"] == {
        "name": 0,
        "nameTie": 0,
        "familyPrefix": 0,
        "familyPrefixTie": 0,
    }
    assert model["excluded"] == {
        "missing-join": 1,
        "zero-position": 1,
    }


def test_single_artifact_is_deterministic_hash_bound_and_mutation_sensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = _server_fixture(tmp_path)
    monkeypatch.setattr(
        generator,
        "_git_source_commit",
        lambda _root, require_clean: "a" * 40,
    )
    first, first_manifest = generator.render_artifacts(server)
    second, second_manifest = generator.render_artifacts(server)
    assert first == second
    assert first_manifest == second_manifest
    assert set(first) == {
        "weakness_data.lua",
        "weakness_data_manifest.json",
    }
    assert first_manifest["includedTargetCount"] == 4
    assert first_manifest["nameCount"] == 8
    assert first_manifest["familyPrefixCount"] == 8
    assert first_manifest["profileCount"] == 1
    assert first["weakness_data.lua"].startswith(
        b"-- SPDX-License-Identifier: GPL-3.0-or-later\n"
    )

    output = tmp_path / "output"
    generator.write_artifacts(output, first)
    validated = generator.validate_output(output)
    assert validated == first_manifest
    generator.check_artifacts(output, first)

    index_path = output / "weakness_data.lua"
    index_path.write_bytes(index_path.read_bytes() + b"-- drift\n")
    with pytest.raises(generator.DataError, match="hash mismatch"):
        generator.validate_output(output)

    generator.write_artifacts(output, first)
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace("  names={\n", "  mobNames={\n"),
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = output / "weakness_data_manifest.json"
    coordinated = json.loads(manifest_path.read_text(encoding="utf-8"))
    coordinated["files"][0]["sha256"] = (
        "sha256:" + hashlib.sha256(index_path.read_bytes()).hexdigest()
    )
    manifest_path.write_text(
        json.dumps(coordinated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(generator.DataError, match="index structure is invalid"):
        generator.validate_output(output)


def test_typical_profile_prefers_frequency_then_lowest_id() -> None:
    selected, counts = generator._typical_profiles(
        {
            "common": generator.Counter({2: 3, 1: 1}),
            "tie": generator.Counter({3: 2, 2: 2}),
        }
    )
    assert selected == {"common": 2, "tie": 2}
    assert counts == {"ambiguous": 2, "ties": 1}


def test_name_normalization_is_lowercase_whitespace_and_underscore_stable() -> None:
    assert generator.normalize_name("  Proof_RABBIT  Echo ") == "proof rabbit echo"


def test_clean_source_gate_covers_every_material_source_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        if "rev-parse" in command:
            return SimpleNamespace(returncode=0, stdout="a" * 40 + "\n")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(generator.subprocess, "run", fake_run)
    assert generator._git_source_commit(tmp_path, require_clean=True) == "a" * 40
    material = calls[1][calls[1].index("--") + 1 :]
    assert set(relative for relative, _table in generator.SQL_TABLES.values()) <= set(material)
    assert set(generator.SEMANTIC_SOURCE_FILES) <= set(material)
    assert "scripts/zones" not in material
    assert "scripts/mixins/zones" not in material
