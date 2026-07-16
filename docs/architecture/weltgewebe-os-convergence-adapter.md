---
id: docs.architecture.weltgewebe-os-convergence-adapter
title: Weltgewebe OS Convergence Adapter
doc_type: architecture
status: active
canonicality: supporting
lifecycle_state: active
summary: Read-only adapter boundary for producing public konvergenzregelkreis Assessment Request v1 objects without duplicating Weltgewebe, Bureau or Chronik truth.
role: norm
organ: governance
owner: governance
last_reviewed: 2026-07-16
review_after: 2026-10-16
depends_on:
  - architecture.weltgewebe-os
  - docs.specs.federation-core
relations:
  - type: relates_to
    target: architecture/weltgewebe-os.md
  - type: relates_to
    target: docs/specs/federation-core.md
  - type: relates_to
    target: docs/blueprints/weltgewebe-os-masterplan.md
verifies_with:
  - scripts/ci/tests/test_convergence_adapter_contract.py
---

# Weltgewebe OS Convergence Adapter

## Purpose

`scripts/convergence/weltgewebe_convergence_adapter.py` is a local read-only adapter from a versioned Weltgewebe input profile to the public konvergenzregelkreis `Assessment Request v1`.

The pinned public protocol head is:

```text
83ed435bf9eb490e81a6ff2103b6c1397440d40b
```

The input profile and adapter envelope carry that `protocol_head`. The emitted request does not. A public request remains the exact protocol object with `schema_version: 1`, `risk_level: R0|R1|R2|R3`, `observation`, `classification`, `effects`, `verifications` and optional `closure`.

## Contract Surface

The only local schema truth is:

- `contracts/convergence/v1.0.0/assessment-profile.schema.json`

No local request schema is authoritative. The request shape is owned by the public `heimgewebe/konvergenzregelkreis` repository, specifically `protocol/assessment-request.v1.schema.json`, its referenced receipt schemas and `profiles/R2.v1.json` at the pinned head above. The adapter nevertheless contains an explicit defensive mirror of that pinned v1 surface: exact nested keys, enums, cardinalities, schema-declared uniqueness, RFC 3339 timestamps, integer schema versions, finite JSON values and the pinned R2 evidence requirements. This executable mirror is compatibility and supply-chain guard code, not a second protocol authority. CI checks every mirrored key and enum set against an exact detached checkout of the pinned public commit and then runs the protocol-owned evaluator. Evaluator acceptance remains decisive.

The deterministic terminal conformance fixtures are:

- `contracts/convergence/v1.0.0/fixtures/conformance.terminal.profile.json`
- `contracts/convergence/v1.0.0/fixtures/conformance.terminal.request.json`

`conformance.terminal.request.json` is the pure public request, not the adapter envelope.

## Authority Boundary

The adapter has exactly these local effects:

- parse a local profile file;
- reject duplicate JSON keys, non-finite JSON constants and forbidden embedded payload keys;
- canonicalize an in-memory public Assessment Request v1;
- compute a SHA-256 digest over canonical request JSON;
- print the selected output to stdout.

The adapter must not call Bureau, Chronik, Grabowski, GitHub, Docker, Kubernetes or production services. It must not write receipts, update task state, append event history, deploy, roll back or mark acceptance. A successful adapter run is only a local request-building proof. The profile and intent digests bind the bytes used for request construction, but they do not authenticate an author. Provenance is established externally by the hash-bound Grabowski execution receipt.

## Reference Boundary

The input profile may model objective, desired state, observed state, deviation, decision and rollback in domain-neutral text. It must not copy Bureau task payloads, Chronik histories, Grabowski receipt bodies or Weltgewebe domain objects.

The public request carries external truth only as protocol references and digests:

- Bureau task authority is mapped into `observation.source_refs` and `closure.bureau_task_ref`.
- Chronik event evidence is mapped into `observation.source_refs` and `closure.chronik_event_ref`.
- Grabowski live receipt evidence is mapped into `observation.source_refs`, verification evidence and closure cleanup evidence.
- The exact Weltgewebe commit or deploy receipt is mapped into `observation.source_refs` and `effects`.

## Rollback And Negative Control

Rollback is not executed by this adapter. Rollback is represented as:

- a passing `verification` with `kind: recovery`;
- closure cleanup evidence;
- a residual-risk reference that names the external rollback execution boundary.

Negative control is represented as a passing `verification` with `kind: negative_control`. The adapter rejects profiles that try to embed mutable external payloads or symbolic Git revisions in source references, effect and verification evidence, or closure references.

## Evaluator Compatibility

The regression test `scripts/ci/tests/test_convergence_adapter_contract.py` reads the protocol checkout from `KONVERGENZREGELKREIS_ROOT`. CI creates that checkout in the runner's temporary directory, fetches only the exact commit `83ed435bf9eb490e81a6ff2103b6c1397440d40b`, verifies `HEAD`, and treats a missing or different checkout as failure. Local development falls back to `/home/alex/repos/konvergenzregelkreis` and may skip only the four protocol integration tests when no checkout is available.

The mirror test compares the adapter's request keys, nested receipt keys, enums and R2 requirements directly with the pinned schemas and profile. The positive request must then evaluate to `terminally_closed` under the public R2 profile. A request missing required evidence must block with `evidence_missing`. A request with conflicting receipt hashes must block with `conflicting_evidence`. A request with adapter metadata such as `protocol_head` at top level must be rejected by the public request schema.

## CLI Shape

Default output is an adapter envelope:

```sh
python3 scripts/convergence/weltgewebe_convergence_adapter.py PROFILE.json
```

The envelope contains adapter metadata, `protocol_head`, the pure public request, `request_sha256`, `profile_sha256` and a separate `intent_sha256`. It intentionally contains no generated-at timestamp: identical input must produce identical output. Freshness and replay decisions belong to the request's `observation.observed_at`, the referenced receipts and the external evaluator; an adapter-local clock field would not provide replay protection.

For the request alone:

```sh
python3 scripts/convergence/weltgewebe_convergence_adapter.py PROFILE.json --output request
```

For the request hash alone:

```sh
python3 scripts/convergence/weltgewebe_convergence_adapter.py PROFILE.json --output hash
```

Live acceptance is outside this repository-local adapter. The public evaluator or installed acceptance command is the only authority for transition assessment.

## Synthetic fixture safety

`conformance.terminal.profile.json` is protocol-conformant test data, not a live T013 receipt. It sets `evidence_mode: synthetic_fixture`; every evidence reference starts with `fixture:` and the observation explicitly states that it establishes no live evidence, deployment acceptance, Bureau closure, Chronik import, or Grabowski execution.

A real acceptance profile must set `evidence_mode: live`. The adapter rejects `fixture:` references in live mode and rejects non-fixture references in synthetic mode. This prevents a terminal conformance fixture from being reused as operational closure evidence.
