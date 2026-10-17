"""Tests for shared guide environment helpers."""

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_SH = REPO_ROOT / "guides" / "env.sh"


def _run_install(tmp_path: Path, *, managed: bool) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl_log = tmp_path / "kubectl.log"
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${KUBECTL_LOG}"

if [[ "$1" == "get" ]]; then
  if [[ "${KUBECTL_MANAGED}" == "true" && "${*: -1}" == *component-name* ]]; then
    printf 'gateway-api-crds'
    exit 0
  fi
  if [[ "${KUBECTL_MANAGED}" == "true" && "${*: -1}" == *bundle-version* ]]; then
    printf 'v1.4.0'
    exit 0
  fi
  exit 1
fi
"""
    )
    kubectl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "GAIE_VERSION": "v1.6.2",
            "KUBECTL_LOG": str(kubectl_log),
            "KUBECTL_MANAGED": str(managed).lower(),
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        }
    )
    result = subprocess.run(
        ["bash", "-c", f'source "{ENV_SH}" && install_gaie_crds'],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, kubectl_log.read_text()


def test_install_gaie_crds_skips_gke_managed_crd(tmp_path: Path) -> None:
    result, calls = _run_install(tmp_path, managed=True)

    assert result.returncode == 0
    assert "GKE manages the InferencePool CRD" in result.stdout
    assert "effective bundle: v1.4.0" in result.stdout
    assert "apply -f" not in calls


def test_install_gaie_crds_applies_to_unmanaged_cluster(tmp_path: Path) -> None:
    result, calls = _run_install(tmp_path, managed=False)

    assert result.returncode == 0
    assert result.stdout == ""
    assert (
        "apply -f https://github.com/kubernetes-sigs/"
        "gateway-api-inference-extension/releases/download/v1.6.2/"
        "v1-manifests.yaml"
    ) in calls
