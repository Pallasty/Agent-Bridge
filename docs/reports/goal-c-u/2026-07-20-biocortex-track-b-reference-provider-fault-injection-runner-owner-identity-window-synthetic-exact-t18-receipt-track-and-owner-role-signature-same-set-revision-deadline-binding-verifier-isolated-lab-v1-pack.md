# BioCortex Track B T19 synthetic owner identity/window verifier

Pure offline KAT: T18 is called once, then six detached synthetic owner/window identities are matched exactly. Any mismatch is fail-closed as `E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED`; no real owner, signature, deadline, network, provider, runtime, or production state is accessed.
