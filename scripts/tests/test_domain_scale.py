#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.performance import domain_scale  # noqa: E402


CONFIG = ROOT / "configs/performance/domain-scale.v1.json"


class DomainScaleTests(unittest.TestCase):
    def test_config_requires_the_reserved_benchmark_schema(self) -> None:
        config = domain_scale.load_config(CONFIG)
        self.assertEqual(config["database_schema"], domain_scale.BENCHMARK_SCHEMA)
        for schema in ("public", "pg_catalog", "information_schema", "other_benchmark"):
            with self.subTest(schema=schema):
                unsafe = dict(config)
                unsafe["database_schema"] = schema
                with self.assertRaisesRegex(domain_scale.DomainScaleError, "reserved benchmark schema"):
                    domain_scale.validate_config(unsafe)

    def test_smoke_fixture_is_deterministic_and_has_exact_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            manifest_a = domain_scale.generate_fixture(CONFIG, "smoke", first)
            manifest_b = domain_scale.generate_fixture(CONFIG, "smoke", second)
            self.assertEqual(manifest_a, manifest_b)
            for filename in ("domain_nodes.csv", "domain_edges.csv", "manifest.json"):
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())

            with (first / "domain_nodes.csv").open(encoding="utf-8", newline="") as handle:
                node_rows = list(csv.DictReader(handle))
            with (first / "domain_edges.csv").open(encoding="utf-8", newline="") as handle:
                edge_rows = list(csv.DictReader(handle))
            self.assertEqual(len(node_rows), 1000)
            self.assertEqual(len(edge_rows), 5000)
            self.assertTrue(all(row["source_id"] != row["target_id"] for row in edge_rows))
            node_ids = {row["id"] for row in node_rows}
            self.assertEqual({row["source_id"] for row in edge_rows}, node_ids)
            self.assertEqual({row["target_id"] for row in edge_rows}, node_ids)

    def test_load_sql_isolated_to_benchmark_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            domain_scale.generate_fixture(CONFIG, "smoke", fixture)
            output = root / "load.sql"
            domain_scale.render_load_sql(fixture / "manifest.json", output)
            sql = output.read_text(encoding="utf-8")
            self.assertIn("DROP SCHEMA IF EXISTS weltgewebe_perf CASCADE", sql)
            self.assertIn("LIKE public.domain_nodes INCLUDING ALL", sql)
            self.assertIn("LIKE public.domain_edges INCLUDING ALL", sql)
            self.assertNotIn("DROP SCHEMA IF EXISTS public", sql)
            self.assertNotIn("TRUNCATE", sql.upper())
            self.assertNotIn("DELETE FROM public", sql)
            self.assertEqual(sql.count("COMMIT;"), 1)
            self.assertLess(sql.index("\\copy weltgewebe_perf.domain_edges"), sql.index("COMMIT;"))

    def test_workload_sql_renders_all_format_json_plans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            plans = root / "plans"
            domain_scale.generate_fixture(CONFIG, "smoke", fixture)
            output = root / "workload.sql"
            domain_scale.render_workload_sql(fixture / "manifest.json", plans, output)
            sql = output.read_text(encoding="utf-8")
            self.assertEqual(sql.count("EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)"), 6)
            for workload in domain_scale.WORKLOAD_ORDER:
                self.assertIn(f"{workload}.json", sql)

    def test_plan_checker_accepts_index_plans_and_rejects_seq_scan(self) -> None:
        config = domain_scale.load_config(CONFIG)
        good_plan = [
            {
                "Plan": {
                    "Node Type": "Limit",
                    "Temp Read Blocks": 0,
                    "Temp Written Blocks": 0,
                    "Plans": [{"Node Type": "Index Scan", "Relation Name": "domain_nodes"}],
                },
                "Planning Time": 0.2,
                "Execution Time": 1.5,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            plan_dir = Path(directory)
            for workload in domain_scale.WORKLOAD_ORDER:
                (plan_dir / f"{workload}.json").write_text(
                    json.dumps(good_plan), encoding="utf-8", newline="\n"
                )
            report = domain_scale.check_plans(config, plan_dir, "scale_100k")
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["budget_enforced"])
            self.assertTrue(report["calibration_required"])

            bad_plan = [
                {
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Temp Read Blocks": 0,
                        "Temp Written Blocks": 0,
                    },
                    "Planning Time": 0.1,
                    "Execution Time": 10.0,
                }
            ]
            (plan_dir / "node_cursor.json").write_text(
                json.dumps(bad_plan), encoding="utf-8", newline="\n"
            )
            with self.assertRaisesRegex(domain_scale.DomainScaleError, "Seq Scan"):
                domain_scale.check_plans(config, plan_dir, "scale_100k")

            observation = domain_scale.check_plans(config, plan_dir, "smoke")
            self.assertEqual(observation["status"], "pass")
            self.assertFalse(observation["budget_enforced"])
            self.assertIn("Seq Scan", observation["workloads"]["node_cursor"]["node_types"])

    def test_manifest_detects_fixture_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            domain_scale.generate_fixture(CONFIG, "smoke", fixture)
            with (fixture / "domain_nodes.csv").open("a", encoding="utf-8") as handle:
                handle.write("tampered\n")
            with self.assertRaisesRegex(domain_scale.DomainScaleError, "hash mismatch"):
                domain_scale.load_manifest(fixture / "manifest.json")


if __name__ == "__main__":
    unittest.main()
