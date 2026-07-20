# S21B-A17 independent-review minimum

S21B-A17 defines the minimum structural shape for a future independent review
evidence packet. It requires separate 64-hex digests for reviewer identity,
subject identity, review scope, and review evidence; reviewer and subject must
be different. The validator also requires explicit non-live and non-acceptance
fields.

The repository fixture is synthetic and intentionally has
`accepted_for_capability_change=false`. Passing the validator proves only that
the packet has the minimum non-self-certifying shape. It is not a real review,
does not identify an external reviewer, does not satisfy A16, and cannot issue
authority, admit input, or unlock execution.
