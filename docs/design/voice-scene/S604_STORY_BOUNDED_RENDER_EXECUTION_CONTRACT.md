# S604 Story bounded-render execution contract

S604 defines the fail-closed boundary between the installed non-actuating
Story preflight and any future audio executor. It hash-binds the accepted S602
preflight, the S603 owner-accepted render, and the audited ONNX runner. The
fixture pilot is limited to three segments, 100 codec frames per segment,
30 seconds assembled audio, 24 kHz mono output, CPU-only offline inference,
and a dedicated evidence-root child directory with no overwrite permission.

Render and playback require separate single-use grants. A playback grant is
not sufficient until a machine audio gate has produced a render receipt and
audio hash. Recording and memory writes are unsupported. The state sequence is
preflight review, render grant, bounded render, machine gate, playback grant,
single playback, and owner feedback.

The contract builder is static. It creates no directory, loads no model,
executes no ONNX graph, renders or plays no audio, and writes no cache or
memory. S604 therefore does not implement or admit a runtime executor. The
next gate is a source-only implementation review of such an executor.
