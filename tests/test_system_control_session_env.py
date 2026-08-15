import json
import os
import pathlib
import socket
import stat
import subprocess
import tempfile
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ab-system-control.sh"


class SystemControlSessionEnvTests(unittest.TestCase):
    def _write_executable(self, path: pathlib.Path, body: str) -> None:
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def test_status_hydrates_validated_graphical_session_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            runtime = root / "runtime"
            fake_bin = root / "bin"
            runtime.mkdir()
            fake_bin.mkdir()

            sockets = []
            for name in ("bus", "sway.sock", "wayland-test"):
                sock = socket.socket(socket.AF_UNIX)
                sock.bind(str(runtime / name))
                sockets.append(sock)
            self.addCleanup(lambda: [sock.close() for sock in sockets])

            self._write_executable(
                fake_bin / "systemctl",
                f"""
                #!/bin/sh
                if [ "$1 $2" = "--user show-environment" ]; then
                    printf '%s\\n' \\
                        'SWAYSOCK={runtime / "sway.sock"}' \\
                        'WAYLAND_DISPLAY=wayland-test' \\
                        'DISPLAY=:77'
                    exit 0
                fi
                exit 0
                """,
            )
            self._write_executable(
                fake_bin / "swaymsg",
                f"""
                #!/bin/sh
                [ "${{SWAYSOCK:-}}" = '{runtime / "sway.sock"}' ] || {{ printf '[]\\n'; exit 0; }}
                printf '%s\\n' '[{{"name":"TEST-1","active":true,"power":true,"focused":true}}]'
                """,
            )
            self._write_executable(
                fake_bin / "pactl",
                """
                #!/bin/sh
                case "$*" in
                    'get-sink-volume @DEFAULT_SINK@') printf '%s\\n' 'Volume: front-left: 26214 / 40% / -23.88 dB' ;;
                    'get-sink-mute @DEFAULT_SINK@'|'get-source-mute @DEFAULT_SOURCE@') printf '%s\\n' 'Mute: no' ;;
                esac
                """,
            )
            self._write_executable(fake_bin / "nmcli", "#!/bin/sh\nexit 0\n")
            self._write_executable(fake_bin / "brightnessctl", "#!/bin/sh\nprintf '%s\\n' 'dev,backlight,1,40%'\n")
            self._write_executable(fake_bin / "upower", "#!/bin/sh\nexit 0\n")
            self._write_executable(fake_bin / "pgrep", "#!/bin/sh\nexit 1\n")

            env = {
                "HOME": str(root),
                "PATH": f"{fake_bin}:/usr/bin:/bin",
                "XDG_RUNTIME_DIR": str(runtime),
                "AB_SYSTEM_CONTROL_AUDIT_DIR": str(root / "audit"),
            }
            proc = subprocess.run(
                ["bash", str(SCRIPT), "status", "summary"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(proc.stdout)

            self.assertEqual(payload["display"], {
                "outputs_total": 1,
                "outputs_active": 1,
                "outputs_powered": 1,
                "focused_output": "TEST-1",
            })
            self.assertEqual(payload["audio"], {
                "volume": "40%",
                "muted": "no",
                "mic_muted": "no",
            })

    def test_audio_status_returns_typed_default_device_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            self._write_executable(
                fake_bin / "pactl",
                """
                #!/bin/sh
                case "$*" in
                    'get-sink-volume @DEFAULT_SINK@') printf '%s\n' 'Volume: front-left: 27525 / 42% / -22.75 dB' ;;
                    'get-sink-mute @DEFAULT_SINK@') printf '%s\n' 'Mute: yes' ;;
                    'get-source-mute @DEFAULT_SOURCE@') printf '%s\n' 'Mute: no' ;;
                    *) exit 2 ;;
                esac
                """,
            )
            env = {
                "HOME": str(root),
                "PATH": f"{fake_bin}:/usr/bin:/bin",
                "AB_SYSTEM_CONTROL_AUDIT_DIR": str(root / "audit"),
            }
            proc = subprocess.run(
                ["bash", str(SCRIPT), "audio", "status"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(json.loads(proc.stdout), {
                "schema": "agent_bridge.system_control.audio_status.v0",
                "read_only": True,
                "backend": "pactl",
                "volume_percent": 42,
                "muted": True,
                "mic_muted": False,
            })


if __name__ == "__main__":
    unittest.main()
