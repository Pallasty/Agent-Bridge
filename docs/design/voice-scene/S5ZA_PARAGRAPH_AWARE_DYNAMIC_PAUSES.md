# S5ZA paragraph-aware dynamic pauses

S5ZA replaces S5Z's fixed 0.8-second gaps with an explicit, bounded structural
policy: same-paragraph continuation is 0.65 seconds, speaker turn is 1.0,
paragraph break is 1.4, and scene break is 2.2. The source parser or story
planner must provide one of these labels; the audio assembler does not infer a
dramatic pause from free-form text and fails closed on unknown labels.

The current excerpt uses paragraph break, speaker turn, then paragraph break,
producing gaps of 1.4, 1.0, and 1.4 seconds. It reuses the four hash-identical
S5Z segment WAVs, so no TTS model ran and voice quality did not change. The
result is 18.92 seconds, finite and non-silent, and its combined SenseVoice
transcript matches the S5Z combined transcript exactly. Machine validation does
not establish good pacing; owner playback remains the admission gate.
