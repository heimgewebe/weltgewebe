from __future__ import annotations

import shlex
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
        min_free_space_rc: int = 0,
        min_free_space_output: str = "",
        fallback_rc: int = 0,
        fallback_output: str = "",
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        start = script.index("measure_available_build_bytes() {")
        end = script.index("\nfetch_main() {", start)
        functions = script[start:end]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pruned = root / "pruned"
            prune_calls = root / "prune-calls"
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
FAKE_PRUNE_CALLS={str(prune_calls)!r}
FAKE_AVAILABLE_BEFORE={available_before}
FAKE_AVAILABLE_AFTER={available_after}
FAKE_ACTIVE={active}
FAKE_SIZE={size!r}
FAKE_RECLAIMABLE={reclaimable!r}
FAKE_MIN_FREE_SPACE_RC={min_free_space_rc}
FAKE_MIN_FREE_SPACE_OUTPUT={shlex.quote(min_free_space_output)}
FAKE_FALLBACK_RC={fallback_rc}
FAKE_FALLBACK_OUTPUT={shlex.quote(fallback_output)}
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
    printf '%s\\n' "$*" >> "$FAKE_PRUNE_CALLS"
    if [[ "$4" == "--min-free-space" ]]; then
      printf '%s' "$FAKE_MIN_FREE_SPACE_OUTPUT" >&2
      if [[ "$FAKE_MIN_FREE_SPACE_RC" != "0" ]]; then
        return "$FAKE_MIN_FREE_SPACE_RC"
      fi
    elif [[ "$4" == "--filter" && "$5" == "until=168h" ]]; then
      printf '%s' "$FAKE_FALLBACK_OUTPUT" >&2
      if [[ "$FAKE_FALLBACK_RC" != "0" ]]; then
        return "$FAKE_FALLBACK_RC"
      fi
    else
      echo "unexpected builder prune invocation: $*" >&2
      return 97
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
            calls = (
                prune_calls.read_text(encoding="utf-8").splitlines()
                if prune_calls.exists()
                else []
            )
            return result, calls

    def test_incident_is_recovered_with_bounded_build_cache_prune(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        guard = script.index('ensure_production_build_disk_headroom "$target_commit"')
        self.assertLess(guard, script.index("docker run --rm", guard))
        self.assertIn("WELTGEWEBE_PRODUCTION_BUILD_MIN_FREE_BYTES", script)
        self.assertIn("51539607552", script)
        self.assertIn("docker system df --format '{{json .}}'", script)
        self.assertNotIn("docker buildx", script)
        self.assertIn(
            'docker builder prune --force --min-free-space "$BUILD_MIN_FREE_BYTES"',
            script,
        )
        self.assertIn(
            "docker builder prune --force --filter until=168h",
            script,
        )
        for forbidden in (
            "docker builder prune --all",
            "docker system prune",
            "docker volume prune",
            "docker image prune",
            "docker container prune",
            "docker image rm",
            "docker rmi",
        ):
            self.assertNotIn(forbidden, script)

        result, calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            calls, ["builder prune --force --min-free-space 51539607552"]
        )
        self.assertIn("build_cache_reclaimable_bytes=196400000000", result.stdout)
        self.assertIn(
            "action=prune scope=unused_build_cache_only policy=min_free_space",
            result.stdout,
        )
        self.assertIn(
            "operation=min_free_space capability=supported",
            result.stdout,
        )
        self.assertIn("action=continue result=cleanup_sufficient", result.stdout)

    def test_known_backend_incompatibility_uses_exact_bounded_fallback(self) -> None:
        result, calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
            min_free_space_rc=1,
            min_free_space_output=(
                "ERROR: rpc error: buildkit v0.17.0+ is required for "
                "max-used-space and min-free-space filters (backend rejected request)"
            ),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            calls,
            [
                "builder prune --force --min-free-space 51539607552",
                "builder prune --force --filter until=168h",
            ],
        )
        self.assertIn(
            "operation=min_free_space capability=unsupported",
            result.stdout,
        )
        self.assertIn(
            "action=prune scope=unused_build_cache_only policy=unused_for_168h",
            result.stdout,
        )
        self.assertIn("production_disk_preflight=post_cleanup", result.stdout)

    def test_arbitrary_prune_error_fails_closed_without_fallback(self) -> None:
        unknown_error = (
            "ERROR: daemon unavailable for min-free-space prune\n"
            "request-id=unknown " + ("x" * 600) + " SECRET_TAIL"
        )
        result, calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
            min_free_space_rc=2,
            min_free_space_output=unknown_error,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            calls, ["builder prune --force --min-free-space 51539607552"]
        )
        self.assertIn("operation=min_free_space capability=unknown", result.stdout)
        self.assertIn("production_disk_preflight=post_cleanup", result.stdout)
        self.assertIn(
            "result=failed policy=min_free_space_unknown exit_code=2",
            result.stdout,
        )
        error_records = [
            line
            for line in result.stderr.splitlines()
            if line.startswith(
                "production_disk_preflight_error=min_free_space_unknown "
            )
        ]
        self.assertEqual(len(error_records), 1, result.stderr)
        self.assertIn(
            "ERROR: daemon unavailable for min-free-space prune", error_records[0]
        )
        self.assertIn(r"\nrequest-id=unknown", error_records[0])
        self.assertFalse(
            any(
                line.startswith("request-id=unknown")
                for line in result.stderr.splitlines()
            )
        )
        self.assertNotIn("SECRET_TAIL", result.stderr)

    def test_active_or_unreclaimable_cache_fails_closed(self) -> None:
        active, active_calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=1,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertNotEqual(active.returncode, 0)
        self.assertEqual(active_calls, [])
        self.assertIn("reason=active_build_cache", active.stdout)

        unreclaimable, unreclaimable_calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=60_000_000_000,
            active=0,
            size="10GB",
            reclaimable="0B (0%)",
        )
        self.assertNotEqual(unreclaimable.returncode, 0)
        self.assertEqual(unreclaimable_calls, [])
        self.assertIn("reason=no_reclaimable_build_cache", unreclaimable.stdout)

    def test_cleanup_is_remeasured_and_can_still_fail_closed(self) -> None:
        insufficient, calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=40_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
        )
        self.assertNotEqual(insufficient.returncode, 0)
        self.assertEqual(
            calls, ["builder prune --force --min-free-space 51539607552"]
        )
        self.assertIn("production_disk_preflight=post_cleanup", insufficient.stdout)
        self.assertIn("reason=insufficient_headroom_after_cleanup", insufficient.stdout)

        failed_fallback, failed_fallback_calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=7_800_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
            min_free_space_rc=1,
            min_free_space_output=(
                "buildkit v0.17.0+ is required for max-used-space and "
                "min-free-space filters"
            ),
            fallback_rc=3,
            fallback_output="ERROR: compatibility fallback unavailable",
        )
        self.assertNotEqual(failed_fallback.returncode, 0)
        self.assertEqual(
            failed_fallback_calls,
            [
                "builder prune --force --min-free-space 51539607552",
                "builder prune --force --filter until=168h",
            ],
        )
        self.assertIn(
            "production_disk_preflight=post_cleanup", failed_fallback.stdout
        )
        self.assertIn("policy=unused_for_168h exit_code=3", failed_fallback.stdout)
        self.assertIn(
            "ERROR: compatibility fallback unavailable", failed_fallback.stderr
        )

        healthy, healthy_calls = self.run_guard(
            available_before=60_000_000_000,
            available_after=60_000_000_000,
            active=3,
            size="20GB",
            reclaimable="5GB (25%)",
            required=51_539_607_552,
        )
        self.assertEqual(healthy.returncode, 0, healthy.stderr)
        self.assertEqual(healthy_calls, [])
        self.assertIn("action=none result=sufficient_headroom", healthy.stdout)

    def test_successful_compatibility_fallback_still_blocks_below_48_gib(self) -> None:
        result, calls = self.run_guard(
            available_before=7_800_000_000,
            available_after=40_000_000_000,
            active=0,
            size="196.4GB",
            reclaimable="196.4GB",
            min_free_space_rc=1,
            min_free_space_output=(
                "buildkit v0.17.0+ is required for max-used-space and "
                "min-free-space filters"
            ),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            calls,
            [
                "builder prune --force --min-free-space 51539607552",
                "builder prune --force --filter until=168h",
            ],
        )
        self.assertIn("production_disk_preflight=post_cleanup", result.stdout)
        self.assertIn("reason=insufficient_headroom_after_cleanup", result.stdout)

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
