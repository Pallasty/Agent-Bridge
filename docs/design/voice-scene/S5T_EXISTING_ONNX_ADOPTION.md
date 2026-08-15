# S5T existing ONNX adoption

S5T changes the active implementation lane after owner review: use the already
downloaded community ONNX snapshot first, and retain fixed-source re-export as
a fallback rather than a prerequisite.

## Why the lane can advance

The current repository evidence already proves more than file presence:

- S5G hashed the complete 36.2 GB snapshot and found all six variant
  inventories complete.
- S5H created CPU ONNX Runtime sessions for all seven CPU INT4 graphs.
- S5I through S5M executed bounded deterministic component probes.
- S5N connected talker cache, code predictor, and residual embedding through
  one deterministic codec frame and one cache feedback step.
- S5R independently verified that the retained original weight payload equals
  the official fixed-revision weight hashes.

Therefore another export is not required to answer the next practical
question: whether the existing ONNX snapshot can synthesize an intelligible
Chinese waveform.

## Active and fallback lanes

The active lane is `community_cpu_int4`. The multi-gigabyte conversion
wheelhouse, Olive installation, fixed-source FP32/INT4 re-export, and re-export
parity work are paused. They resume only if existing ONNX quality,
compatibility, or lineage prevents adoption.

The original model is retained unchanged as a fixed-revision-equivalent
fallback and future reference. S5T does not load it.

## Remaining practical gap

The existing isolated ONNX Runtime environment already contains ONNX Runtime
1.28.0 and NumPy. It lacks Transformers, SoundFile, and Librosa, which the
community inference driver uses for tokenizer access, WAV writing, and
optional resampling.

Those missing runtime packages are a much smaller inference-runtime problem,
not authorization to materialize the multi-gigabyte conversion wheelhouse.
No package installation occurs in S5T.

The next gate may prepare only the minimal existing-ONNX runtime, inspect the
community inference driver without importing it as trusted project code, and
run a bounded text-to-WAV trial into a new isolated output directory. Playback
remains separately owner-authorized.

## Retained claim boundaries

The downloaded snapshot still has mutable-revision, standalone-license, and
untrusted-community-Python blockers. S5T does not claim publisher lineage,
production admission, end-to-end synthesis, MI50 compatibility, or human
audibility.
