# S5X story voice mapping

S5X maps stable S1 story speaker identities to Qwen CustomVoice speakers and
bounded style instructions. It does not infer gender or personality from a
name: the assignments are explicit reviewable inputs.

The fixture mapping is:

- narrator / `旁白` → Vivian, owner accepted;
- `林默` → Dylan, audition pending;
- `苏岚` → Serena, audition pending.

Each role receives a version-2 voice profile and a stability key bound to the
story source SHA-256, S1 speaker ID, Qwen speaker, and profile version.
Repeating the same inputs produces the same mapping and hash. A profile change
must increment the version and repeat audition.

Named roles require explicit one-to-one assignments. Missing roles, invented
Qwen speakers, reuse of one voice across named roles, unbounded style
instructions, unapproved voices, frame-cap truncation, or incomplete ASR all
fail closed.

Only Vivian is currently owner accepted. Therefore
`chapter_render_ready=false`; S5X performs no synthesis or playback. The next
gate should audition the Dylan and Serena role lines independently before a
three-role story excerpt can be rendered.
