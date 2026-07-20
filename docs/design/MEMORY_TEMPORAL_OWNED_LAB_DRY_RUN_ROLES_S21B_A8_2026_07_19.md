# BioCortex Track B S21B-A8: four-role non-live dry-run protocol

Date: 2026-07-19

S21B-A8 adds one exact command, `--dry-run-protocol-v1`, to each named role
artifact while retaining the no-argument A1 identity surface. The protocol is a
deterministic transition chain: controller, observer, runner, validator. It
does not accept paths or payloads, read external input, access credentials,
open a network, launch a child, issue a capability or unlock side effects.

The validator always ends in `ADMISSION_DENIED_FAIL_CLOSED`. Any other argument
is rejected with exit status 64. This stage validates role dispatch and packet
shape only; it is not an operational experiment runner or live admission.
