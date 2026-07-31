# S5Z three-role story excerpt

S5Z adds a fail-closed renderer contract for a continuous four-segment scene:
Vivian narrates, Dylan voices 林默, Serena voices 苏岚, and Vivian closes the
scene. The renderer binds the S5X mapping to the S5Y owner acceptance before it
creates a render plan. It then assembles only mono PCM16 24 kHz segments and
inserts an exact 0.8-second silence at each role transition.

All admitted segments naturally emitted EOS below the 100-frame cap. A first
Serena attempt using `等等，我听见钟声了。` reached the cap and was rejected
without writing a WAV; the retained line preserves the meaning and uses the
previously owner-accepted bounded wording. This is durable evidence that the
real path fails closed rather than silently truncating speech.

SenseVoice found all four story segments in the combined audio. It made one
combined-ASR homophone substitution (`渐近` to `渐静`), and the isolated closing
narration read `尘封` as `尘风` even though combined ASR recovered `尘封`.
Therefore content presence is machine-verified, but verbatim ASR is not claimed.
Human judgments about transitions, character continuity, pacing, and overall
naturalness remain pending playback feedback.
