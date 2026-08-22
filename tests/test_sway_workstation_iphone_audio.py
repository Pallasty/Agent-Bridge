import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup-sway-workstation.sh"


def extract_heredoc(source: str, marker: str) -> str:
    match = re.search(rf"<<'{re.escape(marker)}'\n(.*?)\n{re.escape(marker)}", source, re.S)
    assert match is not None, f"missing heredoc {marker}"
    return match.group(1) + "\n"


class SwayWorkstationIphoneAudioTests(unittest.TestCase):
    def test_iphone_audio_recovery_contract_is_portable(self) -> None:
        source = SETUP.read_text()

        self.assertIn("bluez libspa-0.2-bluetooth usbmuxd libimobiledevice-utils uxplay", source)
        self.assertIn("agentbridge-airplay.service", source)
        self.assertIn("agentbridge-iphone-usb.timer", source)
        self.assertIn(
            "ExecStart=/usr/bin/uxplay -n AgentBridge-%H -nh -vs 0 -as pulsesink -nohold -reset 10",
            source,
        )
        self.assertIn("ipv4.method auto ipv4.never-default yes", source)
        self.assertIn("ipv6.method auto ipv6.never-default yes", source)
        self.assertIn('"${driver_path##*/}" = "ipheth"', source)

        # Hardware identity and one-time Bluetooth bond material belong to the
        # restored node, not to the repository bootstrap.
        self.assertNotIn("64:B0:A6:76:3D:41", source)
        self.assertNotIn("enx66b0a6763d40", source)

    def test_generated_iphone_usb_helper_discovers_ipheth_and_builds_profile(self) -> None:
        source = SETUP.read_text()
        helper_source = extract_heredoc(source, "SWAY_IPHONE_AUDIO_SETUP")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            helper = tmp_path / "sway-iphone-audio-setup"
            helper.write_text(helper_source)
            helper.chmod(0o755)

            subprocess.run(["bash", "-n", str(helper)], check=True)

            drivers = tmp_path / "drivers"
            ipheth_driver = drivers / "ipheth"
            ipheth_driver.mkdir(parents=True)
            net_root = tmp_path / "net"
            iface = net_root / "enx-restored-phone"
            (iface / "device").mkdir(parents=True)
            (iface / "device" / "driver").symlink_to(ipheth_driver, target_is_directory=True)
            (iface / "carrier").write_text("1\n")

            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            nmcli_log = tmp_path / "nmcli.log"
            nmcli = fake_bin / "nmcli"
            nmcli.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >>\"$AB_NMCLI_LOG\"\n"
                "case \"$*\" in\n"
                "  '-g GENERAL.CONNECTION device show '*) printf '%s\\n' '--' ;;\n"
                "esac\n"
            )
            nmcli.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "AB_IPHONE_NET_CLASS_ROOT": str(net_root),
                    "AB_NMCLI_LOG": str(nmcli_log),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                }
            )
            subprocess.run([str(helper)], check=True, env=env)

            calls = nmcli_log.read_text()
            self.assertIn("connection add type ethernet ifname enx-restored-phone", calls)
            self.assertIn("con-name AgentBridge-iPhone-USB", calls)
            self.assertIn("ipv4.method auto ipv4.never-default yes", calls)
            self.assertIn("ipv6.method auto ipv6.never-default yes", calls)
            self.assertIn("connection up AgentBridge-iPhone-USB ifname enx-restored-phone", calls)

    def test_generated_units_and_helper_are_enabled_and_validated(self) -> None:
        source = SETUP.read_text()

        self.assertIn('bash -n "$target_home/.local/bin/sway-iphone-audio-setup"', source)
        self.assertIn("systemctl --user enable --now agentbridge-iphone-usb.timer", source)
        self.assertIn("systemctl --user enable --now agentbridge-airplay.service", source)
        self.assertIn('if [ -x /usr/bin/uxplay ]; then', source)


if __name__ == "__main__":
    unittest.main()
