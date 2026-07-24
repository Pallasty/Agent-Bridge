#!/usr/bin/env python3
"""Fail-closed static source gate for R23 C2C structural assembly."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CARGO = ROOT / "crates/bridge/Cargo.toml"
LIB = ROOT / "crates/bridge/src/lib.rs"
MODULE = ROOT / "crates/bridge/src/episode_observation_c2c_runtime_assembly_synthetic.rs"
MAIN = ROOT / "crates/bridge/src/main.rs"
HUB = ROOT / "crates/bridge/src/hub.rs"


def checks(cargo: str, lib: str, module: str, main: str, hub: str) -> list[tuple[str, bool]]:
    feature = ('episode-observation-c2c-runtime-assembly-synthetic = [\n'
               '    "episode-observation-slice-c2-synthetic",\n]')
    return [
        ("default-off feature depends only on C2 synthetic", feature in cargo),
        ("feature is absent from defaults", "default = [\"onnx-embed\"]" in cargo),
        ("module is feature gated", '#[cfg(feature = "episode-observation-c2c-runtime-assembly-synthetic")]\npub(crate) mod episode_observation_c2c_runtime_assembly_synthetic;' in lib),
        ("authorization is typed and crate-private", "pub(crate) enum EpisodeObservationRuntimeAuthorization" in module),
        ("authorization has disabled and explicit states", all(s in module for s in ("Disabled,", "ExplicitSyntheticLab,"))),
        ("assembler is crate-private", "pub(crate) fn assemble_curation_batch_observer" in module),
        ("only explicit plus present capability passes", "(EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab, Some(capability))" in module),
        ("all other conjunctions return none", "_ => None," in module),
        ("assembler has no provider construction", "synthetic_store_observer" not in module.split("#[cfg(test)]", 1)[0]),
        ("assembler has no I/O or configuration", not any(s in module.split("#[cfg(test)]", 1)[0] for s in ("std::env", "std::fs", "Keychain", "security_framework", "SqliteStore", "tokio::", "clap"))),
        ("tests cover absent conjunctions", "all_incomplete_conjunctions_assemble_nothing" in module),
        ("tests cover bounded synthetic success", "explicit_synthetic_assembly_finalizes_one_bounded_episode" in module),
        ("tests cover disabled and missing no episode", "disabled_or_missing_operands_emit_no_episode" in module),
        ("tests cover begin item close failures", all(s in module for s in ("fail_begin", "fail_item", "fail_close"))),
        ("no public runtime API", "pub fn " not in module and "pub enum " not in module),
        ("no startup wiring token", "episode-observation-c2c" not in main),
        ("no Hub field or builder widening", "episode-observation-c2c" not in hub),
        ("no MCP or raw custody vocabulary", not any(s in module for s in ("MCP", "item_ref", "epoch", "key bytes", "StateStore"))),
    ]


def mutations_fail(cargo: str, lib: str, module: str, main: str, hub: str) -> bool:
    variants = [
        (cargo.replace('"episode-observation-slice-c2-synthetic"', '"other"', 1), lib, module, main, hub),
        (cargo.replace('default = ["onnx-embed"]', 'default = ["onnx-embed", "episode-observation-c2c-runtime-assembly-synthetic"]', 1), lib, module, main, hub),
        (cargo, lib.replace('#[cfg(feature = "episode-observation-c2c-runtime-assembly-synthetic")]\n', '', 1), module, main, hub),
        (cargo, lib, module.replace("Disabled,", "Off,"), main, hub),
        (cargo, lib, module.replace("ExplicitSyntheticLab,", "Implicit,"), main, hub),
        (cargo, lib, module.replace("pub(crate) fn", "pub fn", 1), main, hub),
        (cargo, lib, module.replace("(EpisodeObservationRuntimeAuthorization::ExplicitSyntheticLab, Some(capability))", "(_, Some(capability))", 1), main, hub),
        (cargo, lib, module.replace("_ => None,", "_ => capability,", 1), main, hub),
        (cargo, lib, module.replace("#[cfg(test)]", "synthetic_store_observer\n#[cfg(test)]", 1), main, hub),
        (cargo, lib, module.replace("#[cfg(test)]", "std::env::var(\"BAD\");\n#[cfg(test)]", 1), main, hub),
        (cargo, lib, module.replace("all_incomplete_conjunctions_assemble_nothing", "missing", 1), main, hub),
        (cargo, lib, module.replace("explicit_synthetic_assembly_finalizes_one_bounded_episode", "missing", 1), main, hub),
        (cargo, lib, module.replace("disabled_or_missing_operands_emit_no_episode", "missing", 1), main, hub),
        (cargo, lib, module.replace("fail_close", "close_problem"), main, hub),
        (cargo, lib, module.replace("pub(crate) enum", "pub enum", 1), main, hub),
        (cargo, lib, module, main + "\n// episode-observation-c2c\n", hub),
        (cargo, lib, module, main, hub + "\n// episode-observation-c2c\n"),
        (cargo, lib, module + "\n// StateStore\n", main, hub),
    ]
    return all(not all(ok for _, ok in checks(*variant)) for variant in variants)


def main() -> int:
    values = tuple(path.read_text() for path in (CARGO, LIB, MODULE, MAIN, HUB))
    result = checks(*values)
    for label, ok in result:
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
    mutation_ok = mutations_fail(*values)
    print(f"{'PASS' if mutation_ok else 'FAIL'}: 18 directed mutation checks")
    return 0 if all(ok for _, ok in result) and mutation_ok else 1


if __name__ == "__main__":
    sys.exit(main())
