import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "d82r", HERE / "fh_l8_d60_isolation_transaction_d82r.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[union-attr]


class FakeBackend:
    def __init__(self, euid=0, fail_write=None):
        self._euid = euid
        self.fail_write = fail_write
        self.state = None
        self.dirs = {str(MODULE.CGROUP_ROOT)}
        self.files = {
            str(MODULE.CGROUP_ROOT / "cgroup.controllers"): "cpuset cpu memory",
            str(MODULE.CGROUP_ROOT / "cgroup.subtree_control"): "cpu memory",
            str(MODULE.CGROUP_ROOT / "cpuset.mems.effective"): "0",
            str(MODULE.CPU_ROOT / "online"): "0-15",
            str(MODULE.CPU_ROOT / "cpu15/topology/thread_siblings_list"): "15",
            str(MODULE.IRQ_ROOT / "1/smp_affinity_list"): "0-15",
            str(MODULE.IRQ_ROOT / "2/smp_affinity_list"): "0-14",
        }

    def euid(self):
        return self._euid

    def read(self, path):
        return self.files[str(path)]

    def exists(self, path):
        prefix = str(path)
        return prefix in self.dirs or prefix in self.files

    def mkdir(self, path):
        key = str(path)
        if self.exists(path):
            raise FileExistsError(key)
        self.dirs.add(key)
        for name, value in {
            "cgroup.subtree_control": "",
            "cgroup.procs": "",
            "cpuset.mems": "",
            "cpuset.cpus": "",
            "cpuset.cpus.exclusive": "",
            "cpuset.cpus.partition": "member",
        }.items():
            self.files[str(path / name)] = value

    def rmdir(self, path):
        prefix = str(path) + "/"
        for key in list(self.files):
            if key.startswith(prefix):
                del self.files[key]
        self.dirs.remove(str(path))

    def write(self, path, value):
        key = str(path)
        if self.fail_write == key:
            raise OSError("injected write failure")
        if path.name == "cgroup.subtree_control":
            current = set(self.files[key].split())
            if value.startswith("+"):
                current.add(value[1:])
            elif value.startswith("-"):
                current.discard(value[1:])
            self.files[key] = " ".join(sorted(current))
        else:
            self.files[key] = value

    def irq_paths(self):
        return [
            Path(key)
            for key in sorted(self.files)
            if key.startswith(str(MODULE.IRQ_ROOT)) and key.endswith("smp_affinity_list")
        ]

    def state_exists(self):
        return self.state is not None

    def save_state(self, state):
        self.state = dict(state)

    def load_state(self):
        return self.state

    def delete_state(self):
        self.state = None


class D82RTests(unittest.TestCase):
    def setUp(self):
        self.contract = MODULE.load_json(MODULE.CONTRACT)

    def test_non_root_plan_and_apply_fail_closed(self):
        backend = FakeBackend(euid=1000)
        self.assertIn("host_admin_credential_missing", MODULE.plan(backend, self.contract)["blockers"])
        with self.assertRaisesRegex(MODULE.D82RTransactionError, "host_admin_credential_missing"):
            MODULE.apply(backend, self.contract)

    def test_apply_verify_and_rollback_round_trip(self):
        backend = FakeBackend()
        original_irq = backend.read(MODULE.IRQ_ROOT / "1/smp_affinity_list")
        result = MODULE.apply(backend, self.contract)
        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual(MODULE.verify_applied(backend, self.contract)["status"], "VERIFIED")
        self.assertNotIn(15, MODULE.parse_cpu_list(backend.read(MODULE.IRQ_ROOT / "1/smp_affinity_list")))
        self.assertEqual(MODULE.rollback(backend, self.contract)["status"], "ROLLED_BACK")
        self.assertEqual(backend.read(MODULE.IRQ_ROOT / "1/smp_affinity_list"), original_irq)
        self.assertEqual(backend.read(MODULE.CGROUP_ROOT / "cgroup.subtree_control"), "cpu memory")
        self.assertIsNone(backend.state)

    def test_apply_failure_automatically_rolls_back(self):
        fail_path = str(
            MODULE.CGROUP_ROOT
            / "fh-l8-d60-isolated.slice/fh-l8-d82-measurement.service/cpuset.cpus"
        )
        backend = FakeBackend(fail_write=fail_path)
        with self.assertRaisesRegex(MODULE.D82RTransactionError, "rolled back"):
            MODULE.apply(backend, self.contract)
        self.assertIsNone(backend.state)
        self.assertEqual(backend.read(MODULE.IRQ_ROOT / "1/smp_affinity_list"), "0-15")

    def test_irq_drift_refuses_rollback_without_clobber(self):
        backend = FakeBackend()
        MODULE.apply(backend, self.contract)
        irq_path = MODULE.IRQ_ROOT / "1/smp_affinity_list"
        backend.files[str(irq_path)] = "0-13"
        with self.assertRaisesRegex(MODULE.D82RTransactionError, "IRQ affinity drift"):
            MODULE.rollback(backend, self.contract)
        self.assertEqual(backend.read(irq_path), "0-13")
        self.assertIsNotNone(backend.state)

    def test_populated_service_refuses_rollback(self):
        backend = FakeBackend()
        MODULE.apply(backend, self.contract)
        service = MODULE.CGROUP_ROOT / self.contract["target"]["service_cgroup"]
        backend.files[str(service / "cgroup.procs")] = "4242"
        with self.assertRaisesRegex(MODULE.D82RTransactionError, "populated"):
            MODULE.rollback(backend, self.contract)

    def test_run_requires_applied_green_state(self):
        backend = FakeBackend()
        with self.assertRaisesRegex(MODULE.D82RTransactionError, "applied transaction state"):
            MODULE.validate_run_preconditions(backend, self.contract)
        MODULE.apply(backend, self.contract)
        MODULE.validate_run_preconditions(backend, self.contract)


if __name__ == "__main__":
    unittest.main()
