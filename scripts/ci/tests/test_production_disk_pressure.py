from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[3]


class ProductionDiskPressureTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def run_guard(
        self,
        *,
        available_before: int,
        available_after: int,
        active: int,
        size: str,
        reclaimable: str,
        required: int = 51_539_607_552,
        prune_rc: int = 0,
    ) -> tuple[subprocess.CompletedProcess[str], str | None]:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        start = script.index("measure_available_build_bytes() {")
        end = script.index("\nfetch_main() {", start)
        functions = script[start:end]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pruned = root / "pruned"
            prune_call = root / "prune-call"
            command = f"""set -Eeuo pipefail
SCRIPT_DIR={str(ROOT / "scripts/ops")!r}
run_ops_python() {{
  WELTGEWEBE_OPS_SCRIPT_DIR="$SCRIPT_DIR" python3 -I - "$@"
}}
fail() {{
  echo "ERROR: $*" >&2
  exit 1
}}
ARTIFACT_ROOT={str(root)!r}
BUILD_MIN_FREE_BYTES={required}
FAKE_PRUNED={str(pruned)!r}
FAKE_PRUNE_CALL={str(prune_call)!r}
FAKE_AVAILABLE_BEFORE={available_before}
FAKE_AVAILABLE_AFTER={available_after}
FAKE_ACTIVE={active}
FAKE_SIZE={size!r}
FAKE_RECLAIMABLE={reclaimable!r}
FAKE_PRUNE_RC={prune_rc}
df() {{
  printf 'Avail\\n'
  if [[ -f "$FAKE_PRUNED" ]]; then
    printf '%s\\n' "$FAKE_AVAILABLE_AFTER"
  else
    printf '%s\\n' "$FAKE_AVAILABLE_BEFORE"
  fi
}}
docker() {{
  if [[ "$1" == "system" && "$2" == "df" ]]; then
    printf '{{"Active":"%s","Reclaimable":"%s","Size":"%s","TotalCount":"100","Type":"Build Cache"}}\\n' \\
      "$FAKE_ACTIVE" "$FAKE_RECLAIMABLE" "$FAKE_SIZE"
    return 0
  fi
  if [[ "$1" == "builder" && "$2" == "prune" ]]; then
    printf '%s\\n' "$*" > "$FAKE_PRUNE_CALL"
    if [[ "$FAKE_PRUNE_RC" != "0" ]]; then
      return "$FAKE_PRUNE_RC"
    fi
    : > "$FAKE_PRUNED"
    return 0
  fi
  echo "unexpected docker invocation: $*" >&2
  return 99
}}
{functions}
ensure_production_build_disk_headroom aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
"""
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            call = (
                prune_call.read_text(encoding="utf-8").strip()
                if prune_call.exists()
                else None
            )
            return result, call

    def test_incident_is_recovered_with_bounded_build_cache_prune(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        guard = script.index('ensure_production_build_disk_headroom "$target_commit"')
        self.assertLess(guard, script.index("docker run --rm", guard))
        self.assertIn("WELTGEWEBE_PRODUCTION_BUILD_MIN_FREE_BYTES", script)
        self.assertIn("51539607552", script)
        self.assertIn("docker system df --format '{{json .}}'", script)
        self.assertIn(
            'docker builder prune --force --min-free-space "$BUILD_MIN_FREE_BYTES"',
            script,
        )
        for forbidden in (
            "docker builder prune --all",
            "docker system prune",
            "docker volume prune",
            "docker image prune",
            "docker container prune",
        ):
            self.assertNotIn(forbidden, script)

        result, call = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(call, "builder prune --force --min-free-space 51539607552")
        self.assertIn("build_cache_reclaimable_bytes=196400000000", result.stdout)
        self.assertIn(
            "action=prune scope=unused_build_cache_only policy=min_free_space",
            result.stdout,
        )
        self.assertIn("action=continue result=cleanup_sufficient", result.stdout)

    def test_active_or_unreclaimable_cache_fails_closed(self) -> None:
        active, active_call = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=1,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertNotEqual(active.returncode, 0)
        self.assertIsNone(active_call)
        self.assertIn("reason=active_build_cache", active.stdout)

        unreclaimable, unreclaimable_call = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="10GB",
            reclaimable="0B (0%)",
        )
        self.assertNotEqual(unreclaimable.returncode, 0)
        self.assertIsNone(unreclaimable_call)
        self.assertIn("reason=no_reclaimable_build_cache", unreclaimable.stdout)

    def test_cleanup_is_remeasured_and_can_still_fail_closed(self) -> None:
        insufficient, call = self.run_guard(
            available_before=7_800_000_000,
            available_after=40_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertNotEqual(insufficient.returncode, 0)
        self.assertIsNotNone(call)
        self.assertIn("production_disk_preflight=post_cleanup", insufficient.stdout)
        self.assertIn("reason=insufficient_headroom_after_cleanup", insufficient.stdout)

        healthy, healthy_call = self.run_guard(
            available_before=60_000_000_000,
            available_after=60_000_000_000,
            active=3,
            size="20GB",
            reclaimable="5GB (25%)",
            required=51_539_607_552,
        )
        self.assertEqual(healthy.returncode, 0, healthy.stderr)
        self.assertIsNone(healthy_call)
        self.assertIn("action=none result=sufficient_headroom", healthy.stdout)

    def test_installer_persists_the_48_gib_headroom_policy(self) -> None:
        installer = self.read("scripts/ops/install-production-reconciler.sh")
        reconciler = self.read("scripts/ops/reconcile-production-main-vps.sh")
        for script in (installer, reconciler):
            self.assertIn("WELTGEWEBE_PRODUCTION_BUILD_MIN_FREE_BYTES", script)
            self.assertIn("51539607552", script)
        self.assertIn(
            "printf 'WELTGEWEBE_PRODUCTION_BUILD_MIN_FREE_BYTES=%s\\n'",
            installer,
        )
        self.assertIn("((BUILD_MIN_FREE_BYTES >= 8589934592))", reconciler)


if __name__ == "__main__":
    unittest.main()
