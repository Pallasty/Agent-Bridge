# S5ZE cross-chapter continuity trial

S5ZE selects the three S5ZC segments after the first `scene_break` without
rerendering the accepted first chapter. The generalized chapter selector is
1-based, rejects an unavailable chapter, reports excluded earlier and later
segments, and carries the preceding scene-break pause separately from the
chapter's internal pauses.

Two Vivian lines were generated under the same trusted CPU INT4 ONNX runner as
S5ZD. The hash-identical, previously accepted Serena line was reused. All three
segments naturally emitted EOS below the 100-frame cap. SenseVoice recovered
all non-name content exactly; the only difference was the bounded homophone
`苏岚` / `苏兰`, which proves pronunciation equivalence rather than Hanzi
identity.

The second chapter is a 6.88-second mono PCM16 24 kHz artifact with two exact
1.0-second speaker-turn pauses. It is joined to the already accepted first
chapter using the source-derived 2.2-second scene-break pause. The resulting
20.13-second artifact is finite and non-silent, and its combined ASR retains
all story content subject only to the receipt-bound name homophones.

Owner playback accepted the cross-chapter continuity and the overall result.
The owner noted that the two female voices could be separated further, but
explicitly classified that preference as dependent on novel character settings
and non-blocking for this gate. S5ZE is therefore admitted. This trial neither
registers the production `/story` command nor generalizes quality to arbitrary
chapters; the next gate is a non-actuating `/story` integration preflight.
