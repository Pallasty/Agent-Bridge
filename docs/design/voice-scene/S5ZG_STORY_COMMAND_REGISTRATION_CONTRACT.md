# S5ZG static `/story` registration contract

S5ZG defines the future MCP boundary without modifying the Rust registry. The
proposed tool is `story_command_preflight`, classified as Niche and absent from
all toolset extras, including `codex-essential` and `codex-voice`. A future
registration would additionally require the exact environment opt-in
`AB_STORY_COMMAND_PREFLIGHT_ENABLE=1`; this stage does not evaluate or honor
that switch.

The input accepts only a UTF-8 TXT/Markdown source path, an explicit from-start
or positive chapter selector, and `dry_run=true`. Playback, recording, model
download, memory-write, and other actuation fields do not exist. The contract
hash-binds the accepted S5ZF preflight hash plus its implementation and output
schema. It also hash-binds the exact inspected `mcp_tools.rs` bytes and fails if
the proposed name already appears in that registry source.

The current result proves only that a static, default-hidden registration
contract is reviewable and collision-free for the inspected source snapshot.
It does not compile or register a tool, expose it through `tools/list`, spawn
Python, read a novel through MCP, execute ONNX, render/play audio, or write
cache or memory. The next gate is an isolated in-process preflight adapter;
runtime registration remains separately gated.
