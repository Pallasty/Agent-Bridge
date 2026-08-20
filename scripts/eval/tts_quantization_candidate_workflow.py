#!/usr/bin/env python3
"""Create one offline, non-authorizing TTS quantization candidate audit pack."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import tts_quantization_gate as gate
import tts_quantization_manifest_adapter as adapter


MANIFEST_NAME = "candidate.manifest.json"
RECEIPT_NAME = "candidate.receipt.json"
POLICY_NAME = "gate.policy.json"
INPUT_DIRECTORY = "inputs"


def require_new_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"output_directory_exists:{path}")


def copy_exclusive(source: Path, destination: Path) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer)
    except BaseException:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise


def materialize_inputs(manifest: dict, output_dir: Path, policy: Path) -> Path:
    input_dir = output_dir / INPUT_DIRECTORY
    os.mkdir(input_dir, 0o700)
    policy_copy = output_dir / POLICY_NAME
    copy_exclusive(policy, policy_copy)

    corpus = manifest["corpus"]
    corpus_source = (output_dir / corpus["path"]).resolve()
    corpus_target = input_dir / "corpus.json"
    copy_exclusive(corpus_source, corpus_target)
    corpus["path"] = f"{INPUT_DIRECTORY}/corpus.json"

    for item in manifest["evidence"]:
        source = (output_dir / item["path"]).resolve()
        target = input_dir / f"{item['kind']}.json"
        copy_exclusive(source, target)
        item["path"] = f"{INPUT_DIRECTORY}/{item['kind']}.json"
    return policy_copy


def run(args: argparse.Namespace) -> dict:
    # Validate the frozen policy before creating any output path.
    policy, _ = gate.load_json(args.policy)
    gate.validate_policy(policy)
    require_new_directory(args.output_dir)

    manifest_path = args.output_dir / MANIFEST_NAME
    receipt_path = args.output_dir / RECEIPT_NAME
    adapter_args = argparse.Namespace(**vars(args), output=manifest_path)
    manifest = (
        adapter.adapt_qwen(adapter_args)
        if args.workflow == "qwen-codec-scope3"
        else adapter.adapt_omnivoice(adapter_args)
    )

    os.mkdir(args.output_dir, 0o700)
    policy_copy = materialize_inputs(manifest, args.output_dir, args.policy)
    adapter.write_exclusive(manifest_path, manifest)
    receipt = gate.build_receipt(manifest_path, policy_copy)
    gate.write_exclusive_json(receipt_path, receipt)
    return {
        "workflow": args.workflow,
        "decision": receipt["decision"],
        "manifest": str(manifest_path),
        "receipt": str(receipt_path),
        "self_contained": True,
        "authorization": receipt["authorization"],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="workflow", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--policy", required=True, type=Path)
        subparser.add_argument("--output-dir", required=True, type=Path)

    qwen = subparsers.add_parser("qwen-codec-scope3")
    qwen.add_argument("--waveform", required=True, type=Path)
    qwen.add_argument("--listening", required=True, type=Path)
    qwen.add_argument("--runtime", required=True, type=Path)
    qwen.add_argument("--corpus", required=True, type=Path)
    common(qwen)

    omni = subparsers.add_parser("omnivoice-static-int8")
    omni.add_argument("--summary", required=True, type=Path)
    omni.add_argument("--trajectory", type=Path)
    common(omni)
    return root


def main() -> int:
    cli = parser()
    args = cli.parse_args()
    try:
        summary = run(args)
    except (adapter.AdapterError, gate.ContractError, OSError) as error:
        cli.error(str(error))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
