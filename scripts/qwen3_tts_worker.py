#!/usr/bin/env python3
"""Default-off, single-flight Qwen3-TTS Unix-socket worker for macOS."""
import argparse
import json
import os
import socket
import sys
from pathlib import Path

from qwen3_tts_synth import DEFAULT_MODEL, DEFAULT_SPEAKER, _device_and_dtype

WORKER_PROTOCOL = "ab.tts.worker.v1"
WORKER_ENGINE = "qwen3-pytorch"
WORKER_CAPABILITIES = ["custom_voice", "instruct", "zh"]


def _error(exc):
    return {"ok": False, "protocol": WORKER_PROTOCOL, "backend": "qwen3",
            "engine": WORKER_ENGINE, "detail": str(exc)[:600]}


def _receipt(**fields):
    """Attach the stable worker identity to every reply.

    Clients deliberately do not branch on ``engine``.  It lets a separately
    validated ONNX implementation identify itself while retaining this local
    request/response contract, rather than masquerading as PyTorch Qwen.
    """
    return {"protocol": WORKER_PROTOCOL, "backend": "qwen3",
            "engine": WORKER_ENGINE, "capabilities": WORKER_CAPABILITIES, **fields}


def _receive(conn):
    data = bytearray()
    while len(data) < 65536:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    return json.loads(data.split(b"\n", 1)[0].decode("utf-8"))


def _send(conn, payload):
    conn.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="single-flight Qwen3-TTS local worker")
    ap.add_argument("--socket", required=True)
    ap.add_argument("--model", default=os.environ.get("AB_QWEN3_TTS_MODEL", DEFAULT_MODEL))
    ap.add_argument("--device", choices=["auto", "mps", "cpu"], default=os.environ.get("AB_QWEN3_TTS_DEVICE", "auto"))
    args = ap.parse_args()
    path = Path(args.socket)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() or path.is_socket():
        path.unlink()
    os.umask(0o077)
    try:
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel
        device, dtype = _device_and_dtype(args.device)
        model = Qwen3TTSModel.from_pretrained(args.model, device_map=device, dtype=dtype)
    except Exception as exc:
        print(json.dumps(_error(exc), ensure_ascii=False), flush=True)
        return 1
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(1)
        print(json.dumps(_receipt(ok=True, state="ready", model=args.model,
                                  device=device, dtype=str(dtype).removeprefix("torch.")),
                         ensure_ascii=False), flush=True)
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    request = _receive(conn)
                    if request.get("op") == "health":
                        reply = _receipt(ok=True, state="ready", model=args.model,
                                         device=device, dtype=str(dtype).removeprefix("torch."))
                    elif request.get("op") == "synthesize":
                        text, output = str(request.get("text", "")).strip(), str(request.get("output", "")).strip()
                        if not text or not output:
                            raise ValueError("synthesize requires non-empty text and output")
                        wavs, sample_rate = model.generate_custom_voice(text=text, language="Chinese",
                            speaker=request.get("speaker") or DEFAULT_SPEAKER, instruct=request.get("instruct") or None)
                        sf.write(output, wavs[0], sample_rate)
                        reply = _receipt(ok=True, model=args.model,
                                         voice=request.get("speaker") or DEFAULT_SPEAKER,
                                         sample_rate=sample_rate, device=device,
                                         dtype=str(dtype).removeprefix("torch."),
                                         instruct_applied=bool(request.get("instruct")),
                                         worker="unix_socket")
                    else:
                        raise ValueError("unsupported op")
                except Exception as exc:
                    reply = _error(exc)
                _send(conn, reply)
    finally:
        server.close()
        try: path.unlink()
        except FileNotFoundError: pass


if __name__ == "__main__":
    sys.exit(main())
