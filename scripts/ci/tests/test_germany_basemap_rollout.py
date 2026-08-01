from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STYLE_PATH = REPO / "map-style" / "style-germany.json"
BASEMAP_MODULE = REPO / "apps" / "web" / "src" / "lib" / "map" / "basemap.ts"
GENERATOR = REPO / "apps" / "web" / "scripts" / "generate-basemap-config.js"
BUILD_SCRIPT = REPO / "scripts" / "basemap" / "build-germany-pmtiles.sh"
PREPARE_SCRIPT = REPO / "scripts" / "basemap" / "prepare-germany-rollout.sh"
ACTIVATE_SCRIPT = REPO / "scripts" / "basemap" / "activate-germany-basemap.sh"
HAMBURG_BUILD_SCRIPT = REPO / "scripts" / "basemap" / "build-hamburg-pmtiles.sh"
SCHLESWIG_BUILD_SCRIPT = (
    REPO / "scripts" / "basemap" / "build-schleswig-holstein-pmtiles.sh"
)


class GermanyBasemapRolloutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))

    def test_germany_style_declares_one_nationwide_pmtiles_source(self) -> None:
        self.assertEqual(
            self.style["sources"],
            {
                "basemap-germany": {
                    "type": "vector",
                    "url": "pmtiles://basemap-germany.pmtiles",
                }
            },
        )
        self.assertEqual(
            self.style["metadata"]["weltgewebe:variant"], "germany"
        )

    def test_germany_style_has_required_visual_layers(self) -> None:
        source_layers = {
            layer["source-layer"]
            for layer in self.style["layers"]
            if layer.get("source") == "basemap-germany"
        }
        self.assertEqual(
            source_layers,
            {
                "landcover",
                "landuse",
                "water",
                "transportation",
                "building",
                "place",
            },
        )
        layer_ids = [layer["id"] for layer in self.style["layers"]]
        self.assertEqual(len(layer_ids), len(set(layer_ids)))

    def test_style_version_matches_shared_cache_contract(self) -> None:
        module = BASEMAP_MODULE.read_text(encoding="utf-8")
        version = self.style["metadata"]["weltgewebe:version"]
        self.assertIn(f'LOCAL_BASEMAP_STYLE_VERSION = "{version}"', module)
        self.assertIn("LOCAL_BASEMAP_GERMANY_STYLE_URL", module)
        self.assertIn("style-germany.json", module)

    def test_build_generator_defaults_to_regional_and_binds_identity(self) -> None:
        generator = GENERATOR.read_text(encoding="utf-8")
        self.assertIn(
            'const DEFAULT_LOCAL_BASEMAP_VARIANT = "regional"', generator
        )
        self.assertIn('["regional", "germany"]', generator)
        self.assertIn("PUBLIC_BASEMAP_VARIANT", generator)
        self.assertIn("source_commit", generator)
        self.assertIn("style_sha256", generator)
        self.assertIn("PUBLIC_SOURCE_COMMIT", generator)
        self.assertIn("basemap-build.json", generator)

    def test_builder_requires_complete_valid_snapshot_provenance(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "OSM_FILE_WAS_SET",
            "OSM_URL_WAS_SET",
            "OSM_SHA256_WAS_SET",
            "OSM_SNAPSHOT_DATE_WAS_SET",
        ):
            self.assertIn(marker, builder)
        self.assertIn('case "$SNAPSHOT_OVERRIDE_COUNT"', builder)
        self.assertIn("dt.date.fromisoformat", builder)
        self.assertIn("dt.datetime.now(dt.timezone.utc).date()", builder)
        self.assertIn("OSM_SNAPSHOT_DATE lies in the future", builder)
        self.assertLess(
            builder.index("dt.date.fromisoformat"), builder.index("if ! docker")
        )

    def test_builder_never_replaces_version_or_activates_alias(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("versioned output already exists", builder)
        self.assertIn('"activation": "opt-in"', builder)
        self.assertNotIn('mv -f "$PARTIAL_PMTILES"', builder)
        self.assertNotIn("ln -s", builder)
        self.assertNotIn("PUBLIC_BASEMAP_VARIANT=germany", builder)

    def test_builder_publishes_artifact_and_metadata_as_signal_safe_pair(
        self,
    ) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        docker_at = builder.index('if ! docker "${DOCKER_ARGS[@]}"')
        publish_at = builder.index(
            'ln "$PARTIAL_PMTILES_PATH" "$FINAL_PMTILES_PATH"'
        )
        build_region = builder[docker_at:publish_at]
        self.assertIn('--output="/data/$PARTIAL_PMTILES"', build_region)
        self.assertNotIn('--output="/data/$OUTPUT_PMTILES"', build_region)
        self.assertNotIn('mv "$PARTIAL_PMTILES" "$OUTPUT_PMTILES"', builder)

        function_start = builder.index("publish_immutable_pair() {")
        ignore_signals = builder.index("trap '' INT TERM", function_start)
        artifact_link = builder.index(
            'ln "$PARTIAL_PMTILES_PATH" "$FINAL_PMTILES_PATH"',
            ignore_signals,
        )
        artifact_owned = builder.index("FINAL_ARTIFACT_CREATED=1", artifact_link)
        metadata_link = builder.index(
            'ln "$PARTIAL_META_PATH" "$FINAL_META_PATH"', artifact_owned
        )
        metadata_owned = builder.index("FINAL_META_CREATED=1", metadata_link)
        publication_complete = builder.index("PUBLISH_COMPLETE=1", metadata_owned)
        restore_interrupt = builder.index(
            "trap on_interrupt INT", publication_complete
        )
        restore_terminate = builder.index(
            "trap on_terminate TERM", restore_interrupt
        )

        self.assertLess(ignore_signals, artifact_link)
        self.assertLess(artifact_link, artifact_owned)
        self.assertLess(artifact_owned, metadata_link)
        self.assertLess(metadata_link, metadata_owned)
        self.assertLess(metadata_owned, publication_complete)
        self.assertLess(publication_complete, restore_interrupt)
        self.assertLess(restore_interrupt, restore_terminate)

    def test_prepare_publishes_bound_version_without_alias_switch(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        validation_at = prepare.index("validate:pmtiles")
        envelope_at = prepare.index("germany-pmtiles-prepared-validation-v1")
        publish_at = prepare.index('ln "$ARTIFACT_TMP" "$TARGET_ARTIFACT"')
        self.assertLess(validation_at, envelope_at)
        self.assertLess(envelope_at, publish_at)
        self.assertIn('"artifact": {', prepare)
        self.assertIn('"sha256": os.environ["ARTIFACT_SHA256"]', prepare)
        self.assertIn("ALIAS_ARTIFACT_STATE_BEFORE", prepare)
        self.assertIn("ALIAS_ARTIFACT_STATE_AFTER", prepare)
        self.assertIn("Stable aliases were NOT changed", prepare)
        self.assertNotIn("publish-basemap.sh", prepare)

    def test_prepare_creates_only_the_documented_default_target(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("TARGET_DIR_EXPLICIT=0", prepare)
        self.assertIn('TARGET_DIR="$REPO_ROOT/build/basemap"', prepare)
        self.assertIn('if [[ "$TARGET_DIR_EXPLICIT" == "0" ]]; then', prepare)
        self.assertIn('mkdir -p "$TARGET_DIR"', prepare)
        self.assertIn("explicit target directory does not exist", prepare)
        self.assertIn(
            "GERMANY_BASEMAP_TARGET_DIR must not be empty when set", prepare
        )

    def test_prepare_publication_is_signal_safe_until_verified(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        function_start = prepare.index("publish_immutable_set() {")
        ignore_signals = prepare.index("trap '' INT TERM", function_start)
        artifact_link = prepare.index(
            'ln "$ARTIFACT_TMP" "$TARGET_ARTIFACT"', ignore_signals
        )
        artifact_owned = prepare.index("ARTIFACT_CREATED=1", artifact_link)
        proof_link = prepare.index('ln "$PROOF_TMP" "$TARGET_PROOF"', artifact_owned)
        proof_owned = prepare.index("PROOF_CREATED=1", proof_link)
        meta_link = prepare.index('ln "$META_TMP" "$TARGET_META"', proof_owned)
        meta_owned = prepare.index("META_CREATED=1", meta_link)
        restore_interrupt = prepare.index("trap on_interrupt INT", meta_owned)
        restore_terminate = prepare.index("trap on_terminate TERM", restore_interrupt)
        compare_at = prepare.index('cmp -s "$META" "$TARGET_META"')
        aliases_verified_at = prepare.index("ALIAS_META_STATE_AFTER")
        publication_complete = prepare.index("PUBLISH_COMPLETE=1", compare_at)

        self.assertLess(ignore_signals, artifact_link)
        self.assertLess(artifact_link, artifact_owned)
        self.assertLess(artifact_owned, proof_link)
        self.assertLess(proof_link, proof_owned)
        self.assertLess(proof_owned, meta_link)
        self.assertLess(meta_link, meta_owned)
        self.assertLess(meta_owned, restore_interrupt)
        self.assertLess(restore_interrupt, restore_terminate)
        self.assertLess(compare_at, publication_complete)
        self.assertLess(aliases_verified_at, publication_complete)

    def test_activation_revalidates_checkout_and_freshness_before_aliases(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        marker = (
            "# Re-evaluate checkout and freshness immediately before the first "
            "externally visible change."
        )
        second_check_at = activate.index(marker)
        switch_at = activate.index("if ! switch_alias_pair; then")
        self.assertLess(second_check_at, switch_at)
        between = activate[second_check_at:switch_at]
        self.assertIn("verify_checkout_clean", between)
        self.assertIn("verify_snapshot_freshness", between)
        self.assertIn("invalidate_activation_receipt", between)
        self.assertIn("ACTIVATION_TRANSACTION_OPEN=1", between)
        transaction_at = between.index("ACTIVATION_TRANSACTION_OPEN=1")
        receipt_at = between.index("invalidate_activation_receipt")
        self.assertLess(transaction_at, receipt_at)

    def test_activation_binds_prepared_report_by_artifact_content(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("prepared validation artifact binding mismatch", activate)
        self.assertIn('prepared.get("artifact", {})', activate)
        self.assertIn('"name": artifact.name', activate)
        self.assertIn('"sha256": expected_sha256', activate)
        self.assertIn('"size_bytes": expected_size', activate)
        self.assertNotIn("prepared validation archive path mismatch", activate)

    def test_activation_binds_device_proof_to_clean_frontend_style_and_time(
        self,
    ) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        for contract in (
            "frontend_commit",
            "style_sha256",
            "proofed_at",
            "GERMANY_BASEMAP_RELEASE_PROOF_MAX_AGE_HOURS",
            "desktop-maplibre",
            "ipad-maplibre",
            "five-region-visual",
            "no-external-map-requests",
            "staging-caddy-range",
        ):
            self.assertIn(contract, activate)
        self.assertIn("Germany release proof frontend commit mismatch", activate)
        self.assertIn("Germany release proof style hash mismatch", activate)
        self.assertIn("Germany release proof is too old", activate)
        self.assertIn('git -C "$REPO_ROOT" diff --quiet', activate)
        self.assertIn('git -C "$REPO_ROOT" diff --cached --quiet', activate)
        self.assertIn("ls-files --others --exclude-standard", activate)
        self.assertIn("apps/web map-style policies/performance.v1.json", activate)
        self.assertIn("untracked frontend or style inputs", activate)
        self.assertNotIn("git status --porcelain", activate)

    def test_activation_bounds_all_public_readbacks(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("GERMANY_BASEMAP_HTTP_CONNECT_TIMEOUT_SECONDS", activate)
        self.assertIn("GERMANY_BASEMAP_HTTP_MAX_TIME_SECONDS", activate)
        self.assertIn("--connect-timeout", activate)
        self.assertIn("--max-time", activate)
        self.assertIn('curl "${CURL_COMMON[@]}"', activate)
        self.assertIn("within the readback deadline", activate)

    def test_activation_public_readback_errors_use_explicit_if_blocks(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if ! PUBLIC_META_PATH="$PUBLIC_META"', activate)
        self.assertIn("python3 << 'PY'; then", activate)
        self.assertIn('if ! HTTP_STATUS="$(curl "${CURL_COMMON[@]}"', activate)
        self.assertNotIn("python3 << 'PY' ||\n", activate)

    def test_activation_alias_switch_and_receipt_are_rollback_bound(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ALIASES_TOUCHED=1", activate)
        self.assertIn("restore_alias_pair", activate)
        self.assertIn("ACTIVATION_TRANSACTION_OPEN=1", activate)
        self.assertIn("ACTIVATION_COMMITTED=1", activate)
        self.assertIn("ROLLBACK_IN_PROGRESS=1", activate)
        self.assertIn("ROLLBACK_COMPLETE=1", activate)
        self.assertIn("trap on_exit EXIT", activate)
        self.assertIn("trap on_interrupt INT", activate)
        self.assertIn("trap on_terminate TERM", activate)
        self.assertIn("if ! switch_alias_pair; then", activate)
        self.assertIn("if ! write_activation_receipt; then", activate)
        self.assertIn("if ! verify_activation_receipt; then", activate)
        self.assertIn("could not persist the Germany activation receipt", activate)
        self.assertIn('deploy_frontend_variant "regional"', activate)

    def test_activation_fallback_invalidates_stale_success_receipt(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        rollback_start = activate.index("rollback_activation() {")
        rollback_end = activate.index("cleanup_tmp() {", rollback_start)
        rollback = activate[rollback_start:rollback_end]
        self.assertIn("invalidate_activation_receipt", rollback)
        self.assertIn('rm -f -- "$ACTIVATION_RECEIPT"', activate)
        receipt_at = activate.index("invalidate_activation_receipt", rollback_start)
        regional_at = activate.index(
            'deploy_frontend_variant "regional"', rollback_start
        )
        self.assertLess(receipt_at, regional_at)

    def test_activation_hashes_complete_public_artifact_before_receipt(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        range_at = activate.index("Range: bytes=0-126")
        full_hash_at = activate.index("PUBLIC_ARTIFACT_SHA256")
        receipt_call_at = activate.index("if ! write_activation_receipt; then")
        self.assertLess(range_at, full_hash_at)
        self.assertLess(full_hash_at, receipt_call_at)
        self.assertIn("complete public Germany PMTiles hash mismatch", activate)
        self.assertIn("complete-public-artifact-sha256", activate)

    def test_activation_receipt_heredoc_is_inside_if_statement(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        function_start = activate.index("write_activation_receipt() {")
        function_end = activate.index('[[ "$BASEMAP_VERSION"', function_start)
        receipt_function = activate[function_start:function_end]
        self.assertIn('if ! RECEIPT_PATH="$receipt_tmp"', receipt_function)
        self.assertIn("python3 << 'PY'; then", receipt_function)
        self.assertIn("\nPY\n    rm -f", receipt_function)
        self.assertNotIn("python3 << 'PY' || {", receipt_function)

    def test_hamburg_builder_never_overwrites_a_published_version(self) -> None:
        builder = HAMBURG_BUILD_SCRIPT.read_text(encoding="utf-8")
        docker_at = builder.index("if ! docker run")
        publish_at = builder.index('ln "$PARTIAL_PMTILES_PATH" "$FINAL_PMTILES_PATH"')
        build_region = builder[docker_at:publish_at]
        self.assertIn('--output="/data/$PARTIAL_PMTILES"', build_region)
        self.assertNotIn('--output="/data/$OUTPUT_PMTILES"', build_region)
        self.assertIn("Published version already exists", builder)
        self.assertIn("publish_immutable_pair()", builder)
        self.assertIn("trap '' INT TERM", builder)
        self.assertIn("FINAL_ARTIFACT_CREATED=1", builder)
        self.assertIn("FINAL_META_CREATED=1", builder)
        self.assertIn("PUBLISH_COMPLETE=1", builder)

    def test_schleswig_retries_never_write_or_delete_final_version(self) -> None:
        builder = SCHLESWIG_BUILD_SCRIPT.read_text(encoding="utf-8")
        run_start = builder.index("run_planetiler() {")
        loop_start = builder.index("while true; do")
        publish_at = builder.index('ln "$PARTIAL_PMTILES_PATH" "$FINAL_PMTILES_PATH"')
        retry_region = builder[run_start:publish_at]
        self.assertIn('--output="/data/$PARTIAL_PMTILES"', retry_region)
        self.assertIn('rm -f -- "$PARTIAL_PMTILES_PATH"', retry_region)
        self.assertNotIn('rm -f -- "$FINAL_PMTILES_PATH"', retry_region)
        self.assertNotIn('--output="/data/$OUTPUT_PMTILES"', retry_region)
        self.assertLess(loop_start, publish_at)
        self.assertIn("Published version already exists", builder)
        self.assertIn("PUBLISH_COMPLETE=1", builder)
        self.assertNotIn("ln -s", builder)


if __name__ == "__main__":
    unittest.main()
