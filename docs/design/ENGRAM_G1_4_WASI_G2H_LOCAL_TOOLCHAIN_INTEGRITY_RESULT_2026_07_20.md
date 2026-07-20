# G2H local toolchain integrity result

`G2H_LOCAL_TOOLCHAIN_INTEGRITY_AND_RECOVERY_DECISION` is a public/static,
local-metadata-only receipt.  The checker validates the immutable G2H
contract and does not invoke Cargo, rustup, or any network/build/runtime path.

Result: `FAIL_CLOSED_LOCAL_TOOLCHAIN_NOT_PROVEN`.

The only possible follow-up is a separately reviewed recovery authorization;
G2H itself creates no recovery authority and performs no mutation.
