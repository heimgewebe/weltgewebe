#!/usr/bin/env python3
"""Apply the confirmed, final PR #1445 review follow-ups exactly once."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{relative}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(relative: str, marker: str, addition: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if marker in text:
        raise SystemExit(f"{relative}: marker already present: {marker}")
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def main() -> None:
    deploy = "scripts/ops/deploy-exact-commit-vps.sh"
    replace_once(
        deploy,
        'api_headers=""\nstarted_at=""',
        'api_headers=""\napi_body_file=""\nfrontend_body_file=""\nstarted_at=""',
    )
    replace_once(
        deploy,
        '''require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

fetch_main() {''',
        '''require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

write_bounded_response() {
  local output="$1"
  local limit="$2"
  python3 -c '
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
limit = int(sys.argv[2])
data = sys.stdin.buffer.read(limit + 1)
if len(data) > limit:
    print(f"response exceeds byte limit: more than {limit} bytes", file=sys.stderr)
    raise SystemExit(1)
with path.open("wb") as handle:
    handle.write(data)
    handle.flush()
    os.fsync(handle.fileno())
' "$output" "$limit"
}

fetch_main() {''',
    )
    replace_once(
        deploy,
        '''  if [[ -n "$api_headers" && -f "$api_headers" && ! -L "$api_headers" ]]; then
    rm -f -- "$api_headers"
  fi
  exit "$rc"''',
        '''  local temporary_path
  for temporary_path in "$api_headers" "$api_body_file" "$frontend_body_file"; do
    if [[ -n "$temporary_path" && -f "$temporary_path" && ! -L "$temporary_path" ]]; then
      rm -f -- "$temporary_path"
    fi
  done
  exit "$rc"''',
    )
    replace_once(
        deploy,
        '''api_headers="$(mktemp "$STATE_ROOT/.api-headers.XXXXXX")"
api_body="$(curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors -D "$api_headers" "$API_URL")"
frontend_body="$(curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors "$FRONTEND_URL")"
api_commit="$(jq -er '.commit' <<< "$api_body")"
frontend_commit="$(jq -er '.commit' <<< "$frontend_body")"
[[ "$api_commit" == "$COMMIT" ]] || fail "live API serves $api_commit instead of $COMMIT"
[[ "$frontend_commit" == "$COMMIT" ]] || fail "live frontend serves $frontend_commit instead of $COMMIT"
api_header="$(awk -F': ' 'tolower($1)=="x-weltgewebe-api-build" {gsub("\\r", "", $2); print $2}' "$api_headers")"
edge_header="$(awk -F': ' 'tolower($1)=="x-weltgewebe-build" {gsub("\\r", "", $2); print $2}' "$api_headers")"''',
        '''api_headers="$(mktemp "$STATE_ROOT/.api-headers.XXXXXX")"
api_body_file="$(mktemp "$STATE_ROOT/.api-body.XXXXXX")"
frontend_body_file="$(mktemp "$STATE_ROOT/.frontend-body.XXXXXX")"
if ! curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors -D "$api_headers" "$API_URL" |
  write_bounded_response "$api_body_file" 1048576; then
  fail "live API readback failed or exceeded the byte limit"
fi
if ! curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors "$FRONTEND_URL" |
  write_bounded_response "$frontend_body_file" 1048576; then
  fail "live frontend readback failed or exceeded the byte limit"
fi
api_commit="$(jq -er '.commit' "$api_body_file")"
frontend_commit="$(jq -er '.commit' "$frontend_body_file")"
[[ "$api_commit" == "$COMMIT" ]] || fail "live API serves $api_commit instead of $COMMIT"
[[ "$frontend_commit" == "$COMMIT" ]] || fail "live frontend serves $frontend_commit instead of $COMMIT"
api_header="$(awk -F':' 'tolower($1)=="x-weltgewebe-api-build" {gsub(/^[ \\t]+|[ \\t\\r]+$/, "", $2); print $2}' "$api_headers")"
edge_header="$(awk -F':' 'tolower($1)=="x-weltgewebe-build" {gsub(/^[ \\t]+|[ \\t\\r]+$/, "", $2); print $2}' "$api_headers")"''',
    )

    verifier = "scripts/ops/verify_public_release_commit.py"
    replace_once(
        verifier,
        '''def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}
''',
        '''def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    raw_items = getattr(headers, "raw_items", headers.items)
    for key, value in raw_items():
        normalized_key = str(key).lower()
        normalized_value = str(value)
        existing = normalized.get(normalized_key)
        normalized[normalized_key] = (
            f"{existing}, {normalized_value}" if existing else normalized_value
        )
    return normalized
''',
    )

    validator = "scripts/ops/validate_web_deploy_archive.py"
    replace_once(validator, "DEFAULT_MAX_MEMBERS = 20_000", "DEFAULT_MAX_MEMBERS = 5_000")
    replace_once(
        validator,
        '''        with tarfile.open(path, mode="r:gz") as bundle:
            for member in bundle:
''',
        '''        with tarfile.open(path, mode="r:gz") as bundle:
            if bundle.pax_headers:
                raise ArchiveValidationError("archive has unsupported global pax headers")
            for member in bundle:
''',
    )
    replace_once(
        validator,
        '''                canonical = _canonical_member_name(member)
                if canonical in seen:
''',
        '''                canonical = _canonical_member_name(member)
                if member.pax_headers:
                    raise ArchiveValidationError(
                        f"archive member has unsupported pax headers: {canonical}"
                    )
                if canonical in seen:
''',
    )
    replace_once(
        validator,
        '''                if member.mode & 0o6000:
                    raise ArchiveValidationError(
                        f"elevated permission bits in archive: {canonical}"
                    )
''',
        '''                if member.mode & 0o7022:
                    raise ArchiveValidationError(
                        f"elevated or writable permission bits in archive: {canonical}"
                    )
''',
    )

    archive_tests = "scripts/ci/tests/test_validate_web_deploy_archive.py"
    replace_once(
        archive_tests,
        '''        with self.assertRaisesRegex(ArchiveValidationError, "elevated permission bits"):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_expanded_size_limit''',
        '''        with self.assertRaisesRegex(
            ArchiveValidationError, "elevated or writable permission bits"
        ):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_group_writable_member(self) -> None:
        member = tarfile.TarInfo("build/group-writable.js")
        member.mode = 0o664
        with self.assertRaisesRegex(
            ArchiveValidationError, "elevated or writable permission bits"
        ):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_member_pax_headers(self) -> None:
        member = tarfile.TarInfo("build/pax.js")
        member.pax_headers = {"comment": "unexpected"}
        with self.assertRaisesRegex(ArchiveValidationError, "unsupported pax headers"):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_expanded_size_limit''',
    )

    verifier_tests = "scripts/ci/tests/test_verify_public_release_commit.py"
    replace_once(
        verifier_tests,
        '''EndpointResult = MODULE.EndpointResult
evaluate = MODULE.evaluate
fetch_endpoint = MODULE.fetch_endpoint
validate_commit = MODULE.validate_commit
''',
        '''EndpointResult = MODULE.EndpointResult
_normalize_headers = MODULE._normalize_headers
evaluate = MODULE.evaluate
fetch_endpoint = MODULE.fetch_endpoint
validate_commit = MODULE.validate_commit
''',
    )
    replace_once(
        verifier_tests,
        '''    def test_rejects_oversized_response(self) -> None:
''',
        '''    def test_aggregates_duplicate_headers(self) -> None:
        headers = Message()
        headers["Cache-Control"] = "public"
        headers["Cache-Control"] = "no-store"
        normalized = _normalize_headers(headers)
        self.assertEqual(normalized["cache-control"], "public, no-store")

    def test_rejects_oversized_response(self) -> None:
''',
    )

    contract_tests = "scripts/ci/tests/test_production_reconciler_contract.py"
    replace_once(
        contract_tests,
        '''        self.assertNotIn("curl -fsSI", script)
        self.assertIn("--max-filesize 1048576", script)
''',
        '''        self.assertNotIn("curl -fsSI", script)
        self.assertIn("--max-filesize 1048576", script)
        self.assertIn("write_bounded_response", script)
        self.assertIn('api_body_file="$(mktemp', script)
        self.assertIn("awk -F':'", script)
''',
    )

    append_once(
        "docs/deploy/merge-to-live.md",
        "## Bedrohungsmodell und Beweisgrenzen",
        '''## Bedrohungsmodell und Beweisgrenzen

Der Vertrag schützt gegen einen weiterwandernden `main`-Branch, parallele Reconciler,
manipulierte oder übergroße Webarchive, unerwartete Release-Worktree-Zustände und
einen öffentlichen Readback, der nicht exakt zum Zielcommit passt.

Er setzt weiterhin folgende Vertrauensanker voraus:

- Der root-eigene Git-Objektspeicher auf dem VPS ist unverändert und authentisch.
- Kernel, Docker-Daemon und Root-Kontext des VPS sind nicht kompromittiert.
- Das digestgepinnte Node-Basisimage und die über den Lockfile aufgelösten Pakete
  sind für den Build vertrauenswürdig.
- Der Build darf derzeit aus dem Bridge-Netz laden, weil `pnpm install
  --frozen-lockfile` innerhalb des flüchtigen Containers läuft. Ein vollständig
  netzloser Build benötigt das in `WELTGEWEBE-OS-V1-T015` geplante,
  repositoryeigene Buildimage mit vorab gebundenem Paketbestand.

`SOURCE_DATE_EPOCH`, der vollständige Commit und das digestgepinnte Basisimage
verbessern die Deterministik. Sie beweisen jedoch keine byteidentische
Reproduzierbarkeit des gesamten Node-Ökosystems. Deshalb bindet `verified` den
öffentlich gelesenen Code- und Webartefaktstand, nicht eine unabhängig
reproduzierte Buildgleichheit. Ein kompromittierter VPS-Root kann Receipts und
Laufzeit gleichermaßen manipulieren; dagegen hilft nur eine zusätzliche externe
Attestierungs- und Produktionsidentitätsachse, die in
`WELTGEWEBE-OS-V1-T014` weitergeführt wird.''',
    )


if __name__ == "__main__":
    main()
