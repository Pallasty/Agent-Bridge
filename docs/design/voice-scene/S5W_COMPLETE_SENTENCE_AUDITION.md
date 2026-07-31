# S5W complete-sentence audition

S5W changes the trusted runner's frame cap from a silent truncation mechanism
into a fail-closed completion gate. If generated codec frames equal the cap,
the runner raises an error and writes no WAV. A candidate is eligible only
when generation stops before the cap through the model's EOS path.

The Vivian trial stopped naturally at frame 58 under a 100-frame bound.
SenseVoice recovered the complete requested sentence, with punctuation-only
normalization, and classified its emotion as happy. The 4.64-second WAV passed
finite/non-silent checks and was played under standing owner authorization.

The owner reported `完整！清晰，自然`. S5W therefore accepts this complete
Vivian sentence for audibility, clarity, and naturalness. The claim remains
candidate-specific; story voice mapping is the next gate.
