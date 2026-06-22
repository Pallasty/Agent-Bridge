# Trigger Contrastive Non-Authorization Controls

Date: 2026-06-22
Scope: read-only eval/report only

## Why

The prior negation acceptance probe left one `projected+intent` false hit on the
Mac trigger-aware corpus:

- `hard_nexus_wuxing_art_cjk:nexus_35_tech_wuxing_shengke_v01_20260620@7`

It also called out a remaining falsifier class: English contrastive
non-authorization questions using forms such as `not`, `rather than`, and
`instead of`.

## Change

This slice keeps production retrieval untouched and extends only the eval
harness:

- adds `projected_plus_intent` to the mode contract comment;
- rebases cleanly over the candidate assembly probe from
  `f4259f4` (`projected_union` / `projected_oracle`);
- adds English exclusion markers `rather than` and `instead of`;
- keeps `not` and Chinese `不要`;
- does not add Chinese `不是` or `而不是` as hard exclusion markers, because
  those can appear in positive contrastive questions;
- tightens the Wuxing art hard negative to exclude both math survey and design
  review intent;
- adds four contrastive controls:
  - `contrastive_goal_c_not_executor`
  - `contrastive_graph_rather_than_packet`
  - `contrastive_onsen_instead_handoff`
  - `contrastive_nexus_instead_review`

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval
cargo check -p ab-bridge --all-targets
```

Results:

- `cargo test`: 14 passed.
- Mac corpus size: 30 positive cases.
- Negative controls: 16 controls.
- `projected+intent` positive recall remained R@10 1.000.
- `projected+intent` false hits dropped from 1 to 0.
- Candidate assembly probes stayed neutral:
  `projected_union` and `projected_oracle` each still missed case #27.
- Parser errors stayed 0.

Key eval rows:

```text
projected+intent     0.733   0.967   1.000   0.829
projected+intent ctrl:   0 false hit(s), 0 parser error(s)
```

## Boundary

This remains an eval-only falsifier. It does not change production:

- `memory_search`
- tokenizer/schema/reindex
- runtime ranking
- MCP tools
- graph expansion
- semantic expansion
- memory writes

The result supports a design hypothesis only: explicit exclusion/contrast
clauses can be useful after candidate generation, but still need broader
cross-host corpus checks before any runtime discussion.
