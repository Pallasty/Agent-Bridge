# S5V trusted existing-ONNX audition

S5V replaces direct community-driver invocation with a repository-owned runner.
The runner rejects source-hash drift, forces local-only tokenizer loading,
sets `fix_mistral_regex=True`, hides CUDA/HIP/ROCm devices, and uses greedy
generation for a reproducible audition candidate.

The Vivian candidate generated 60 codec frames and a 4.8-second mono PCM16
24 kHz WAV. SenseVoice recovered `你好，我是小树，请听听这段声音。` with an
RTF of 0.07. The requested suffix was truncated by the 60-frame bound, so this
stage does not claim full-sentence completion.

The owner explicitly authorized playback and reported `清晰，温柔。`. This
promotes audibility, clarity, and a gentle voice impression only for this
candidate. It does not establish all-text naturalness, role coverage, MI50
compatibility, or production admission.

The next gate should replace a fixed frame cap with bounded EOS-aware length
control, require full requested-text ASR coverage, and audition one complete
sentence before integration into the story renderer.
