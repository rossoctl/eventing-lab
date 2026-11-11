import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kind_setup
from proclib import Checks


class KindSetupTests(unittest.TestCase):
    def test_check_reports_missing_kubeconfig(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            kubeconfig = Path(temp_dir) / "config-kind"
            checks = Checks(prefix="kind")
            kind = kind_setup.Kind(
                checks,
                SimpleNamespace(name="kev1", kubeconfig=str(kubeconfig), recreate=False),
            )
            kind.exists = lambda: True
            kind.k.items = lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("kubectl get nodes failed: no such file or directory")
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                kind.check_only()

            self.assertIn("FAIL the kubeconfig", output.getvalue())
            self.assertIn("kind export kubeconfig --name kev1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
