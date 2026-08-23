"""Tests for scripts/performance/postgres_connection_sampler.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.performance import postgres_connection_sampler as sampler  # noqa: E402


class SamplingLoopTests(unittest.TestCase):
    def test_samples_entire_bounded_window(self) -> None:
        clock = {"t": 0.0}
        values = iter([4, 5, 6, 5])

        def monotonic() -> float:
            return clock["t"]

        def sleep(seconds: float) -> None:
            clock["t"] += seconds

        samples = sampler.run_sampling_loop(
            duration_seconds=3.0,
            interval_seconds=1.0,
            read_count=lambda: next(values),
            sleep=sleep,
            monotonic=monotonic,
        )
        self.assertEqual(samples, [4, 5, 6, 5])

    def test_rejects_invalid_window_and_sample(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "duration-seconds"):
            sampler.run_sampling_loop(
                duration_seconds=0,
                interval_seconds=1,
                read_count=lambda: 1,
                sleep=lambda _: None,
                monotonic=lambda: 0.0,
            )
        with self.assertRaisesRegex(sampler.SamplerError, "connection sample"):
            sampler.run_sampling_loop(
                duration_seconds=1,
                interval_seconds=1,
                read_count=lambda: -1,
                sleep=lambda _: None,
                monotonic=lambda: 0.0,
            )


class ReceiptTests(unittest.TestCase):
    def test_build_receipt_records_peak_and_run_identity(self) -> None:
        receipt = sampler.build_receipt(
            run_id="api-runtime-test-run",
            database_container="wg-t048-db-test",
            samples=[4, 6, 5],
            started_at_unix_ms=1000,
            finished_at_unix_ms=2000,
        )
        self.assertEqual(
            receipt,
            {
                "schema_version": 2,
                "contract": "postgres-connection-sample-v2",
                "run_id": "api-runtime-test-run",
                "database_container": "wg-t048-db-test",
                "started_at_unix_ms": 1000,
                "finished_at_unix_ms": 2000,
                "max_connections": 6,
                "sample_count": 3,
                "samples": [4, 6, 5],
            },
        )

    def test_rejects_invalid_run_id_and_samples(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "run-id"):
            sampler.build_receipt(
                run_id="bad run",
                database_container="db",
                samples=[1],
                started_at_unix_ms=1000,
                finished_at_unix_ms=2000,
            )
        with self.assertRaisesRegex(sampler.SamplerError, "invalid"):
            sampler.build_receipt(
                run_id="good-run",
                database_container="db",
                samples=[1, -1],
                started_at_unix_ms=1000,
                finished_at_unix_ms=2000,
            )

    def test_rejects_invalid_wall_clock_window(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "wall-clock interval"):
            sampler.build_receipt(
                run_id="good-run",
                database_container="db",
                samples=[1],
                started_at_unix_ms=2000,
                finished_at_unix_ms=2000,
            )

    def test_atomic_writer_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            payload = sampler.build_receipt(
                run_id="run-1",
                database_container="db",
                samples=[3],
                started_at_unix_ms=1000,
                finished_at_unix_ms=2000,
            )
            sampler.write_atomic_json(path, payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)


class PsqlReadTests(unittest.TestCase):
    @mock.patch("scripts.performance.postgres_connection_sampler.subprocess.run")
    def test_uses_docker_exec_psql_without_shell(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="7\n", stderr="")
        value = sampler.read_connection_count(
            "wg-t048-db-test",
            database_user="welt",
            database_name="weltgewebe",
        )
        self.assertEqual(value, 7)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ["docker", "exec", "wg-t048-db-test"])
        self.assertIn("SELECT count(*) FROM pg_stat_activity;", argv)
        self.assertNotIn("shell", run.call_args.kwargs)

    @mock.patch("scripts.performance.postgres_connection_sampler.subprocess.run")
    def test_rejects_non_integer_psql_output(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="nope\n", stderr="")
        with self.assertRaisesRegex(sampler.SamplerError, "not an integer"):
            sampler.read_connection_count(
                "wg-t048-db-test",
                database_user="welt",
                database_name="weltgewebe",
            )


if __name__ == "__main__":
    unittest.main()
