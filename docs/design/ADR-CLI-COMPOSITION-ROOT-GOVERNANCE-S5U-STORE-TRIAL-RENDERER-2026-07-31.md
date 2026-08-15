# ADR: CLI composition-root governance S5-U store-trial renderer

## Status

Accepted on 2026-07-31.

## Decision

Move only completed `RetrievalOptInStoreTrial` payload rendering to private `cli::biocortex`. Keep input custody, database selection/opening, Store ownership, trial execution, policy and payload construction in `main.rs`.

## Trade-offs and consequences

This removes a presentation block without introducing a typed view model. The renderer remains coupled to the stable JSON contract, while no retrieval, Store, approval, MCP, deployment, or runtime authority crosses the boundary.

## Revisit trigger

Revisit only when the payload contract becomes typed; do not move Store or trial execution for line-count reduction.
