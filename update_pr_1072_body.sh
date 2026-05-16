#!/bin/bash
# Update PR #1072 body with dependency analysis section
# Usage: GH_TOKEN=<token> ./update_pr_1072_body.sh

set -e

if [[ -z "$GH_TOKEN" ]]; then
    echo "Error: GH_TOKEN environment variable not set"
    echo ""
    echo "To update PR #1072 description with dependency analysis:"
    echo ""
    echo "1. Generate a GitHub personal access token at: https://github.com/settings/tokens"
    echo "   (Requires 'repo' scope for public repos)"
    echo ""
    echo "2. Run:"
    echo "   export GH_TOKEN=<your-token-here>"
    echo "   $0"
    echo ""
    exit 1
fi

REPO_OWNER="heimgewebe"
REPO_NAME="weltgewebe"
PR_NUMBER="1072"

# Read the updated body from stdin or file
BODY=$(cat <<'EOF'
## Summary

Narrow, focused implementation of **Auth Phase 5**: Database-backed session storage with direct PostgreSQL persistence. Sessions now survive across server restarts when database is configured.

## Scope

✅ **Implemented:**
- New `DbSessionStore` struct in `apps/api/src/auth/session_db.rs`
- Full `SessionOps` trait implementation (7 async methods)
- Conditional session store initialization in `lib.rs` (DB-backed vs. in-memory)
- Expiry filtering at query time (`WHERE expires_at > NOW()`)
- 5-minute debounce on `touch()` to prevent excessive updates
- Comprehensive integration test suite

❌ **Out of Scope (deferred):**
- UI/frontend changes
- Redis integration
- PgBouncer-specific gates
- Passkey/TokenStore persistence
- Error handling architecture changes

## Pre-Patch Analysis

### Hypotheses Validated

| # | Hypothesis | Status | Finding |
|---|-----------|--------|---------| 
| 1 | SessionBackend accepts custom SessionOps implementations | ✅ | `SessionBackend::new<T>()` generic wrapper exists and is sufficient |
| 2 | lib.rs conditionalizes session store initialization | ⚠️ | Pattern exists (db_pool, nats), but sessions always hardcoded to in-memory |
| 3 | sessions table migration exists | ✅ | Migration files already present: `20260428000000_create_sessions.{up,down}.sql` |
| 4 | Offline tests (no DATABASE_URL) remain green | ✅ | Validated: 146 unit tests pass without DATABASE_URL |
| 5 | ApiState accepts SessionBackend without modification | ✅ | Type stable; no changes required |

## Changes

### Files Modified
- `apps/api/Cargo.toml` (+4 sqlx features: `chrono`, `migrate`, `runtime-tokio`, `postgres`)
- `apps/api/src/auth/mod.rs` (pub mod session_db)
- `apps/api/src/auth/session.rs` (added sqlx::FromRow derive)
- `apps/api/src/lib.rs` (conditional session store initialization + startup migration)

### Files Created
- `apps/api/src/auth/session_db.rs` (DbSessionStore + SessionOps impl)
- `apps/api/tests/db_session_store_persistence.rs` (6 integration tests)

## Architecture

```
SessionBackend (trait wrapper)
  ├── SessionOps (trait: create, get, delete, touch, list_by_account, delete_by_device, delete_all_by_account)
  │   ├── SessionStore (in-memory, RwLock<HashMap>)
  │   └── DbSessionStore (PgPool-backed) ← NEW
  │       └── PostgreSQL sessions table
  └── ApiState { sessions: SessionBackend }
```

### Session Initialization Logic (lib.rs)

```
if db_pool_configured {
    if pool.is_some() {
        Use DbSessionStore + run migrations
        Log: "Session store backed by PostgreSQL database"
    } else {
        return Err: DATABASE_URL configured but pool unavailable
    }
} else {
    Use SessionStore (in-memory)
    Log: "Session store in-memory (database not configured)"
}
```

## Testing & Validation

### Offline Tests (no DATABASE_URL)
- ✅ 146 unit tests pass (cargo test --locked -p weltgewebe-api --lib)
- Syntax: `#[test]` (synchronous, no async runtime or DB)
- Scope: SessionStore in-memory, config, WebAuthn, passkeys, etc.

### Integration Tests (optional, require DATABASE_URL)
Located in `apps/api/tests/db_session_store_persistence.rs`, marked `#[ignore]`.

Run with:
```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test -p weltgewebe-api --test db_session_store_persistence -- --include-ignored
```

Tests included:
1. **db_session_store_persistence** — Sessions persist across DbSessionStore recreation
2. **db_session_store_expiry_filter** — Expired sessions excluded from list_by_account
3. **db_session_store_list_by_account** — Account isolation and expiry filtering
4. **db_session_store_delete_by_device** — delete_by_device removes target account+device sessions only
5. **db_session_store_delete_all_by_account** — delete_all_by_account removes all sessions for target account
6. **db_session_store_touch** — touch respects 5-minute debounce + expiry filtering

### Code Quality
- ✅ `cargo fmt --all -- --check` (PASS)
- ✅ `cargo clippy -p weltgewebe-api --all-targets --all-features -- -D warnings` (PASS)
- ✅ `cargo test --locked -p weltgewebe-api` (146 unit tests PASS, 6 integration tests ignored as expected)
- ✅ `git diff --check` (PASS, no whitespace issues)

## Dependency Footprint Analysis

Enabling `sqlx/migrate` for runtime startup migrations expands the transitive sqlx dependency graph, adding entries to Cargo.lock for `sqlx-mysql`, `sqlx-sqlite`, `libsqlite3-sys`, `rsa`, `sha1`, `num-bigint-dig`, and related crates.

**Linkage Proof:** Using `cargo tree -p weltgewebe-api -i <crate>` on all new transitive crates confirms **none are actively linked to weltgewebe-api at runtime**:

```bash
cargo tree -p weltgewebe-api -i sqlx-mysql     # → nothing to print
cargo tree -p weltgewebe-api -i sqlx-sqlite    # → nothing to print
cargo tree -p weltgewebe-api -i libsqlite3-sys # → nothing to print
cargo tree -p weltgewebe-api -i rsa            # → nothing to print
cargo tree -p weltgewebe-api -i sqlx-macros    # → nothing to print
```

These entries are **metadata-only** in Cargo.lock from sqlx ecosystem feature interdependencies, not runtime dependencies of weltgewebe-api. This expansion is an **accepted cost** of including `sqlx/migrate` for startup migrations as part of Auth Phase 5 requirements.

## Backwards Compatibility

- **Offline scenarios:** Unaffected. Without `DATABASE_URL`, sessions default to in-memory.
- **Existing session queries:** No schema changes; column structure preserved.
- **Expired session handling:** Query-layer filtering at DB time; consistent with SessionStore logic.
- **Touch debounce:** Consistent 5-minute threshold across both backends.
- **Hard error on misconfiguration:** DATABASE_URL set but pool unavailable → explicit error (no silent fallback).

## Deferred Decisions

- Migration execution during CI: relies on existing `.github/workflows/` + db-wait.sh readiness
- PgBouncer compatibility: uses direct Postgres pool; evaluated separately (ADR-0007)
- Observability: no metrics added; monitoring deferred to Gate B

## Next Steps

1. **Merge:** Integrate into `main`
2. **CI Validation:** Full pipeline on merge (tests, migrations, deployment)
3. **Phase 6:** Evaluate Passkey/TokenStore persistence (if needed)
4. **Phase 7:** Optional — Redis caching layer / PgBouncer gate

---

**Branch:** `feature/auth-phase5-db-session-store`  
**Status:** Ready for Review  
**Checklist:** ✅ All pre-patch checks validated, ✅ All tests pass, ✅ Dependency footprint proven, ✅ Code review ready
EOF
)

# Escape for JSON
BODY_JSON=$(jq -R -s '.' <<< "$BODY")

# Make API request
echo "Updating PR #${PR_NUMBER} description..."

RESPONSE=$(curl -s -X PATCH \
  -H "Authorization: token ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/issues/${PR_NUMBER}" \
  -d "{\"body\": ${BODY_JSON}}")

if echo "$RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    echo "✅ PR #${PR_NUMBER} description updated successfully"
    echo ""
    echo "View PR: https://github.com/${REPO_OWNER}/${REPO_NAME}/pull/${PR_NUMBER}"
else
    echo "❌ Failed to update PR:"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
