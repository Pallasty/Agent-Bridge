# S5ZB chapter voice render preflight

S5ZB bridges the static `/story` plan to the accepted Qwen role and pacing
contracts without loading a model or emitting audio. It binds source, mapping,
role acceptance, and pacing acceptance; then derives a deterministic transition
from chapter membership, source-line gaps, and speaker changes. The precedence
is scene break, paragraph break, speaker turn, then same-paragraph continuation.

The real `story_s1.md` dry run produced five ordered segments and correctly
identified the cross-chapter transition as a 2.2-second scene break. It also
found two render blockers: the S1 timeline retains attribution prose around
quoted dialogue. Passing those full lines to Dylan or Serena would make the
characters narrate their own speech tags. The receipt therefore remains
`chapter_render_ready=false`; the next gate is source-grounded utterance
segmentation, not TTS execution.

This stage does not register `/story`, mutate memory, render audio, play audio,
or claim that arbitrary novel dialogue has already been parsed correctly.
