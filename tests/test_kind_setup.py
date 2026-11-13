"""kind_setup.py's kubeconfig guard — a missing file is a reported gap, not a traceback.

Regression tests for #25: `--check` on a cluster that exists but whose kubeconfig was
never exported used to pass its first check and then die inside `check_resources()`
with `RuntimeError: kubectl get nodes failed`. `--check` must report it and touch
nothing; the install path must leave an existing kubeconfig alone.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import kind_setup
from proclib import Checks, Result


def _kind(tmp_path, recreate=False):
    kubeconfig = tmp_path / "config-kind"
    args = SimpleNamespace(name="kev1", kubeconfig=str(kubeconfig), recreate=recreate)
    return kind_setup.Kind(Checks(prefix="kind"), args), kubeconfig


def test_check_reports_missing_kubeconfig(tmp_path, capsys):
    kind, kubeconfig = _kind(tmp_path)
    kind.exists = lambda: True
    kind.clusters = lambda: ["kev1"]
    kind.k.items = mock.Mock(side_effect=AssertionError("kubectl must not be called"))

    kind.check_only()

    out = capsys.readouterr().out
    assert "FAIL the kubeconfig" in out
    assert "kind export kubeconfig --name kev1" in out
    assert not kubeconfig.exists()


def test_install_path_leaves_an_existing_kubeconfig_alone(tmp_path, monkeypatch):
    kind, kubeconfig = _kind(tmp_path)
    kind.clusters = lambda: ["kev1"]
    kubeconfig.write_text("apiVersion: v1\n")
    monkeypatch.setattr(kind_setup, "run",
                        mock.Mock(side_effect=AssertionError("run must not be called")))

    assert kind.create() is True
    assert kubeconfig.read_text() == "apiVersion: v1\n"


def test_install_path_exports_kubeconfig_for_existing_cluster(tmp_path, monkeypatch):
    kind, kubeconfig = _kind(tmp_path)
    kind.clusters = lambda: ["kev1"]
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if list(argv[:3]) == ["kind", "export", "kubeconfig"]:
            Path(argv[argv.index("--kubeconfig") + 1]).write_text("apiVersion: v1\n")
        return Result(argv=tuple(argv), rc=0, out="", err="", duration_s=0.0)

    monkeypatch.setattr(kind_setup, "run", fake_run)

    assert kind.create() is True
    assert kubeconfig.is_file()
    assert ["kind", "export", "kubeconfig", "--name", "kev1",
            "--kubeconfig", str(kubeconfig)] in calls
