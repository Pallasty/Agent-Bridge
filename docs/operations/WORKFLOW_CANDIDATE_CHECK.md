# Check local skill candidate helpers

This optional read-only preflight borrows Harness²'s helper existence and Python
compilation checks. Run it on a candidate copy before a separately authorized
trial. It complements AB's `skills.rs` risk lint; neither check proves that a
skill is safe, loadable, useful or correct at runtime.

```bash
python3 scripts/eval/workflow_candidate_check.py \
  --skill path/to/candidate/SKILL.md \
  --required-script scripts/check.py
```

Repeat `--required-script` for helpers known to be required by the candidate.
Do not declare hypothetical example paths as dependencies. Paths are relative
to the skill directory; `--root` can explicitly allow a larger candidate root.
References must remain inside that root, and symlinks are rejected.

The command:

- Reads the skill and finds literal `scripts/…` references ending in `.py`,
  `.sh`, `.js` or `.ts`, including optional `./` or `../` prefixes.
- Checks explicitly required helpers for existence. Missing required helpers
  fail; missing text-discovered references need review because they may be
  examples. Dynamic or unsupported script references also need review.
- Finds every `.py` helper below the skill's `scripts/` directory and compiles
  its bytes with the current Python interpreter, without executing, importing
  or writing bytecode. Reports the interpreter version and consumed hashes.
- Checks existence only for other referenced languages; their syntax and
  behavior remain unchecked and produce a review finding.

| Status | Exit | Interpretation |
| --- | --- | --- |
| `PASS_SCOPED` | 0 | Recognized references exist and selected Python files compile; only these checks passed |
| `NEEDS_REVIEW` | 1 | Ambiguous/missing textual references, non-Python helpers, dynamic paths or no recognized references |
| `FAIL` | 1 | Required helper missing, Python compilation failure, symlink or file-boundary violation |
| `INVALID_INPUT` | 2 | Invalid entry/root, unreadable skill, or bounded scan limit exceeded |

Exit 0 never means installed, runtime-tested, security-approved or authorized.
No recognized reference yields `NEEDS_REVIEW`, even for a valid instruction-only
skill; this is an applicability limit, not a claim that such a skill is broken.
Other relative paths, Markdown semantics, shell expansion, imports, dependencies,
frontmatter, trigger quality and client-specific loader behavior are not checked.
In particular, AB does not inherit Harness²'s requirement that every skill name
appear in an always-on prompt. A raw text reference may describe an example;
only a caller-declared required script makes its absence a definite error.

Files are limited to 8 MiB each, at most 256 loaded files and a bounded scripts
entry scan. The program shares the bounded file reader from
`workflow_experience_contrast.py`. It is not a hostile-filesystem sandbox, and
does not establish that a later runtime consumes unchanged bytes. It does not
modify candidates, install skills or execute candidate commands.

Once a candidate's structure is acceptable, return to the original delivery
and its existing acceptance checks. If comparable execution evidence already
exists, the [experience contrast review](WORKFLOW_EXPERIENCE_CONTRAST.md) can
help interpret it; static preflight cannot substitute for that evidence or
justify a new experiment by itself.

Validation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p test_workflow_candidate_check.py
```

This is independently written code, inspired by
[Harness² tree validation at 1cfe254e](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/tree.py).
No upstream code/dependency was copied. See the
[implementation report](../reports/2026-10-26-harness2-candidate-check.md).
