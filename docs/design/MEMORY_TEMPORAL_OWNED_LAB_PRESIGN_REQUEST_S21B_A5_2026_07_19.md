# BioCortex Track B S21B-A5: owner presign request

Date: 2026-07-19

This unit creates an external, subject-specific Ed25519 possession and review
request. It binds the owner public key, exact A4 subject, integration commit and
tree, two fresh random nonce hashes, a non-live owner decision, and a framed
binary signing message. Outputs are create-once and mode 0600 inside a mode
0700 external directory.

The requested signature confirms only the exact unsigned subject for the next
non-live review. It does not authorize external-input admission, execution,
reruns, credentials, providers, production access or side effects. The private
key is never accepted by repository tooling.
