# S5ZH same-process story preflight adapter

S5ZH accepts the exact structured S5ZG input and directly invokes the S5ZF
Python function in the same interpreter. The adapter does not construct or
execute a shell pipeline and does not use a child process. Before loading the
preflight module, it revalidates the S5ZG contract digest, the bound preflight
script and schema hashes, the accepted S5ZF hash, and the inspected Rust
registry source hash.

The real chapter-two call returns the original S5ZF preflight hash and three
render requests. Input fields outside `source_path`, `start`, and
`dry_run=true` fail closed. An AST negative control rejects imports or calls
associated with shell and subprocess execution.

This evidence is deliberately Python-scoped. It proves a direct function call
inside one Python process; it does not prove that Agent-Bridge's Rust process
can call Python in-process, that a Rust-native equivalent exists, or that an
MCP tool is registered. It also performs no ONNX inference, synthesis,
playback, cache write, or memory write. The next gate is a Rust in-process
design decision that must choose between a native port and an explicitly
embedded interpreter before any registry change.
