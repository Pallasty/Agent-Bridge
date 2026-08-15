# S602 Story fixture MCP preflight

The installed MCP surface executed a real `story_command_preflight` call for
`fixtures/story_s1.md`, starting at chapter 2 with `dry_run=true`. The tool
returned `story_command_integration_preflight_reviewable` without an MCP error.

The source hash matched the fixture and all four configured evidence files
retained their pre-call hashes. The result selected three chapter-2 segments,
excluded four earlier segments, applied two 1.0-second assembly gaps and the
accepted 2.2-second preceding-scene gap. The bounded render plan assigned
Vivian, Serena, and Vivian in order, with three distinct cache keys.

The result kept `execution_authorized=false` and reported every actuation flag
false: no model load, ONNX execution, audio rendering, playback, memory write,
or cache write. The call did not turn the dry-run plan into a performance or
playback operation. Nine persistent MCP processes remained after the temporary
probe.
