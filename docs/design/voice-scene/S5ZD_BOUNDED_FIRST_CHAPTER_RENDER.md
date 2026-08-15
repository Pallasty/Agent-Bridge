# S5ZD bounded first-chapter Qwen render

S5ZD renders only the four S5ZC segments before the first `scene_break`; three
second-chapter segments remain excluded. The scene-break pause is not appended
to the chapter artifact. Three Vivian segments were generated under the trusted
CPU INT4 ONNX runner, while the byte-identical, previously accepted Dylan line
was reused. All four segments naturally emitted EOS below the 100-frame cap.

SenseVoice recovered every non-name word exactly after punctuation
normalization. Chinese names produced homophones (`默/末/墨`, `岚/兰`, and
`默/莫`). Since audio cannot encode the intended Hanzi, verification uses a
finite, receipt-bound named-entity equivalence list. This proves bounded
pronunciation equivalence, not Hanzi identity; unrelated ASR differences still
fail closed. The verifier independently recomputes every WAV SHA-256 instead of
trusting declared validity.

The four segments are assembled with 0.65, 1.0, and 1.0-second pauses into an
11.05-second mono PCM16 24 kHz artifact. Owner playback accepted it as coherent,
natural, clearly identifiable, and appropriately paced. S5ZD is admitted for
this bounded first chapter. This does not generalize acceptance to arbitrary
chapters or register the production `/story` command; cross-chapter continuity
is the next gate.
