"""Tests for scripts/performance/container_resource_sampler.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.performance import container_resource_sampler as sampler  # noqa: E402


def _sample(cpu_percent: float, memory_bytes: int) -> dict:
    return {
        "cpu_percent": cpu_percent,
        "memory_bytes": memory_bytes,
        "block_read_bytes": 0,
        "block_write_bytes": 0,
        "network_received_bytes": 0,
        "network_transmitted_bytes": 0,
        "pids": 3,
    }


class AccumulatePeaksTests(unittest.TestCase):
    def test_tracks_the_maximum_across_samples(self) -> None:
        samples = [_sample(10.0, 100), _sample(55.5, 90), _sample(20.0, 200)]
        peaks = sampler.accumulate_peaks(samples)
        self.assertEqual(peaks["cpu_percent"], 55.5)
        self.assertEqual(peaks["memory_bytes"], 200)
        self.assertEqual(peaks["sample_count"], 3)

    def test_rejects_empty_sample_list(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "at least one"):
            sampler.accumulate_peaks([])

    def test_rejects_negative_cpu_percent(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "cpu_percent"):
            sampler.accumulate_peaks([_sample(-1.0, 10)])

    def test_rejects_non_integer_memory(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "memory_bytes"):
            sampler.accumulate_peaks([{"cpu_percent": 1.0, "memory_bytes": 1.5}])


class RunSamplingLoopTests(unittest.TestCase):
    def test_samples_at_least_once_and_respects_duration(self) -> None:
        clock = {"t": 0.0}
        sleeps: list[float] = []

        def monotonic() -> float:
            return clock["t"]

        def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            clock["t"] += seconds

        calls = {"n": 0}

        def read_stats(name: str) -> dict:
            calls["n"] += 1
            return _sample(float(calls["n"]), calls["n"] * 10)

        samples = sampler.run_sampling_loop(
            container_name="weltgewebe-api",
            duration_seconds=3.0,
            interval_seconds=1.0,
            read_stats=read_stats,
            sleep=sleep,
            monotonic=monotonic,
        )
        self.assertGreaterEqual(len(samples), 3)
        self.assertTrue(all(s <= 1.0 for s in sleeps))

    def test_brackets_a_short_duration_with_a_start_and_end_sample(self) -> None:
        # duration_seconds shorter than interval_seconds still yields two
        # samples: one immediately, one after sleeping out the remainder, so
        # very short windows are not silently reduced to a single reading.
        state = {"t": 0.0}

        def monotonic() -> float:
            return state["t"]

        def sleep(seconds: float) -> None:
            state["t"] += seconds

        samples = sampler.run_sampling_loop(
            container_name="weltgewebe-api",
            duration_seconds=0.5,
            interval_seconds=5.0,
            read_stats=lambda name: _sample(1.0, 1),
            sleep=sleep,
            monotonic=monotonic,
        )
        self.assertEqual(len(samples), 2)

    def test_rejects_non_positive_duration_or_interval(self) -> None:
        with self.assertRaisesRegex(sampler.SamplerError, "duration-seconds"):
            sampler.run_sampling_loop(
                container_name="x",
                duration_seconds=0,
                interval_seconds=1.0,
                read_stats=lambda name: _sample(1.0, 1),
                sleep=lambda s: None,
                monotonic=lambda: 0.0,
            )
        with self.assertRaisesRegex(sampler.SamplerError, "sample-interval-seconds"):
            sampler.run_sampling_loop(
                container_name="x",
                duration_seconds=1.0,
                interval_seconds=0,
                read_stats=lambda name: _sample(1.0, 1),
                sleep=lambda s: None,
                monotonic=lambda: 0.0,
            )


class BuildReceiptAndWriteTests(unittest.TestCase):
    def test_build_receipt_matches_the_contract_shape(self) -> None:
        receipt = sampler.build_receipt(
            container_name="weltgewebe-api",
            samples=[_sample(30.0, 1000), _sample(10.0, 2000)],
        )
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["contract"], "api-replica-resource-sample-v1")
        self.assertEqual(receipt["container_name"], "weltgewebe-api")
        self.assertEqual(receipt["peaks"], {"cpu_percent": 30.0, "memory_bytes": 2000})
        self.assertEqual(receipt["sample_count"], 2)

    def test_write_atomic_json_round_trips_and_refuses_symlink_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "receipt.json"
            payload = {"a": 1}
            sampler.write_atomic_json(receipt_path, payload)
            self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8")), payload)

            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(sampler.SamplerError, "regular file"):
                sampler.write_atomic_json(link, payload)


class MeasuredContainerModuleReuseTests(unittest.TestCase):
    def test_loads_the_real_run_measured_container_module(self) -> None:
        module = sampler._load_measured_container_module()
        self.assertTrue(callable(module.read_stats))
        self.assertTrue(issubclass(module.MeasurementError, RuntimeError))
        # parse_size/parse_pair are reused (not duplicated) from that script.
        self.assertEqual(module.parse_size("1KiB"), 1024)


if __name__ == "__main__":
    unittest.main()
