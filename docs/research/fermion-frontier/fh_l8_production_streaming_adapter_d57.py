#!/usr/bin/env python3
"""Fail-closed FH-L8 production streaming adapter interfaces.

This module implements record, per-source, spill, merge-plan and publication
interfaces.  It deliberately has no enabled full-53 entrypoint and performs no
filesystem I/O by itself.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Mapping, MutableMapping, Protocol, Sequence


SOURCE_RECORD = struct.Struct(">16sqBBHI")
SPILL_RECORD = struct.Struct(">16sqQ")
SOURCE_RECORD_BYTES = 32
SPILL_RECORD_BYTES = 32
PARTITION_COUNT = 256
MAX_COLUMN_ENTRIES = 225
MAX_MERGE_FAN_IN = 32
FULL53_EXECUTION_AUTHORIZED = False


class AdapterError(RuntimeError):
    pass


class Full53Unauthorized(AdapterError):
    pass


@dataclass(frozen=True)
class SourceRow:
    representative: int
    amplitude: int
    orbit_size: int
    insertion_rank: int


@dataclass(frozen=True)
class SpillRow:
    target: int
    scaled8_delta: int


@dataclass(frozen=True)
class SourceReceipt:
    representative: int
    insertion_rank: int
    column_entries: int
    spill_records: int
    partition_histogram: tuple[tuple[int, int], ...]
    spill_payload_sha256: str
    column_released_before_return: bool


class PartitionSink(Protocol):
    def emit(self, partition: int, payload: bytes) -> None: ...


Kernel = Callable[[int], MutableMapping[int, Fraction]]


def decode_one_source_record(raw: bytes) -> SourceRow:
    if not isinstance(raw, bytes) or len(raw) != SOURCE_RECORD_BYTES:
        raise AdapterError("exactly one 32-byte packed-q3 source record required")
    representative_raw, amplitude, orbit_size, flags, reserved, rank = SOURCE_RECORD.unpack(raw)
    if flags != 0 or reserved != 0:
        raise AdapterError("packed-q3 reserved fields must be zero")
    if amplitude == 0:
        raise AdapterError("packed-q3 zero amplitude is forbidden")
    if orbit_size not in (1, 4, 8):
        raise AdapterError("packed-q3 orbit size outside frozen domain")
    return SourceRow(
        representative=int.from_bytes(representative_raw, "big"),
        amplitude=amplitude,
        orbit_size=orbit_size,
        insertion_rank=rank,
    )


def partition_for_target(target: int) -> int:
    if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target < 1 << 128:
        raise AdapterError("target must be u128")
    return hashlib.sha256(target.to_bytes(16, "big")).digest()[0]


def encode_spill_record(row: SpillRow) -> bytes:
    if not 0 <= row.target < 1 << 128:
        raise AdapterError("spill target outside u128")
    if not -(1 << 63) <= row.scaled8_delta < 1 << 63:
        raise AdapterError("spill coefficient outside signed i64")
    return SPILL_RECORD.pack(
        row.target.to_bytes(16, "big"), row.scaled8_delta, 0
    )


def decode_spill_record(raw: bytes) -> SpillRow:
    if not isinstance(raw, bytes) or len(raw) != SPILL_RECORD_BYTES:
        raise AdapterError("exactly one 32-byte spill record required")
    target_raw, scaled8_delta, reserved = SPILL_RECORD.unpack(raw)
    if reserved != 0:
        raise AdapterError("spill reserved field must be zero")
    return SpillRow(int.from_bytes(target_raw, "big"), scaled8_delta)


def _scaled8(amplitude: int, coefficient: Fraction) -> int:
    scaled = amplitude * coefficient * 8
    if scaled.denominator != 1:
        raise AdapterError("kernel coefficient is not exactly representable at denominator 8")
    value = scaled.numerator
    if not -(1 << 63) <= value < 1 << 63:
        raise AdapterError("scaled spill coefficient outside signed i64")
    return value


def process_one_source(raw: bytes, kernel: Kernel, sink: PartitionSink) -> SourceReceipt:
    """Process one source and release its column on success or failure."""
    source = decode_one_source_record(raw)
    column = kernel(source.representative)
    if not isinstance(column, MutableMapping):
        raise AdapterError("bound kernel must return a mutable mapping")
    hasher = hashlib.sha256()
    histogram: dict[int, int] = {}
    emitted = 0
    entry_count = len(column)
    try:
        if entry_count > MAX_COLUMN_ENTRIES:
            raise AdapterError("column entry count exceeds D52 structural cap")
        for target, coefficient in sorted(column.items()):
            if not isinstance(coefficient, Fraction):
                raise AdapterError("kernel coefficient must be Fraction")
            payload = encode_spill_record(
                SpillRow(target, _scaled8(source.amplitude, coefficient))
            )
            partition = partition_for_target(target)
            sink.emit(partition, payload)
            hasher.update(payload)
            histogram[partition] = histogram.get(partition, 0) + 1
            emitted += 1
    finally:
        column.clear()
    if column:
        raise AdapterError("column release invariant failed")
    return SourceReceipt(
        representative=source.representative,
        insertion_rank=source.insertion_rank,
        column_entries=entry_count,
        spill_records=emitted,
        partition_histogram=tuple(sorted(histogram.items())),
        spill_payload_sha256=hasher.hexdigest(),
        column_released_before_return=True,
    )


def merge_batches(run_names: Sequence[str]) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Return the deterministic at-most-32-way external-merge batch plan."""
    if not run_names or any(not isinstance(name, str) or not name for name in run_names):
        raise AdapterError("nonempty run-name sequence required")
    if len(set(run_names)) != len(run_names):
        raise AdapterError("duplicate merge run name")
    current = tuple(run_names)
    levels: list[tuple[tuple[str, ...], ...]] = []
    while len(current) > 1:
        batches = tuple(
            tuple(current[offset : offset + MAX_MERGE_FAN_IN])
            for offset in range(0, len(current), MAX_MERGE_FAN_IN)
        )
        if any(len(batch) > MAX_MERGE_FAN_IN for batch in batches):
            raise AdapterError("merge fan-in escaped bound")
        levels.append(batches)
        current = tuple(
            f"level-{len(levels):02d}-run-{index:03d}"
            for index in range(len(batches))
        )
    return tuple(levels)


def publication_order() -> tuple[str, ...]:
    partitions = tuple(f"partition-{index:03d}.bin" for index in range(PARTITION_COUNT))
    return (*partitions, "manifest.json", "result.json", "terminal-receipt.json")


def run_full53(*_args: object, **_kwargs: object) -> None:
    raise Full53Unauthorized("D57 implements interfaces but grants no full-53 execution authority")

