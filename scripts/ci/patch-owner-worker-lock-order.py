from pathlib import Path

worker_path = Path("apps/api/src/search/worker.rs")
worker = worker_path.read_text(encoding="utf-8")
lines = worker.splitlines(keepends=True)
marker = "// Private content remains searchable only as an authorized lexical"
marker_indexes = [index for index, line in enumerate(lines) if marker in line]
if len(marker_indexes) != 1:
    raise SystemExit(f"unexpected private worker marker count: {len(marker_indexes)}")
marker_index = marker_indexes[0]
start = next(
    index
    for index in range(marker_index, len(lines))
    if "let written = sqlx::query(" in lines[index]
)
end = next(
    index
    for index in range(start, len(lines))
    if ".rows_affected();" in lines[index]
)
original_write = "".join(lines[start : end + 1])
if original_write.count(".execute(&self.pool)") != 1:
    raise SystemExit("private worker write no longer has one pool execution anchor")
transactional_write = original_write.replace(
    ".execute(&self.pool)", ".execute(&mut *tx)", 1
)
prefix = '''            // Account lifecycle updates lock the account row before they
            // redact projections and bump node versions. Lock the same row first
            // here, before the existing version/job fence, so both paths have one
            // global lock order and cannot deadlock each other.
            let active_owner_account_id = owner_account_id
                .as_deref()
                .context("private projection missing active owner")?;
            let mut tx = self.pool.begin().await?;
            let owner_locked = sqlx::query_scalar::<_, String>(
                "SELECT id FROM domain_accounts WHERE id=$1 AND disabled=FALSE FOR SHARE",
            )
            .bind(active_owner_account_id)
            .fetch_optional(&mut *tx)
            .await?
            .is_some();
            if !owner_locked {
                tx.rollback().await?;
                return Ok(Ok(if self.claim_is_current(job_id, attempts).await? {
                    ProcessOutcome::Stale
                } else {
                    ProcessOutcome::LeaseLost
                }));
            }
'''
suffix = "            tx.commit().await?;\n"
lines[start : end + 1] = [prefix + transactional_write + suffix]
worker_path.write_text("".join(lines), encoding="utf-8")

test_path = Path("apps/api/tests/db_semantic_search_owner_lifecycle.rs")
test_text = test_path.read_text(encoding="utf-8")
test_name = "private_worker_locks_owner_before_projection_state"
if test_name in test_text:
    raise SystemExit("real worker lock-order proof already exists")
proof = r'''

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn private_worker_locks_owner_before_projection_state() {
    let pool = pool().await;
    migrate(&pool).await;
    reset(&pool).await;

    sqlx::query("INSERT INTO domain_accounts (id,title,disabled) VALUES ($1,'Eigentümer',FALSE)")
        .bind(OWNER_ID)
        .execute(&pool)
        .await
        .expect("create active owner for worker race proof");
    sqlx::query(
        "INSERT INTO domain_nodes \
         (id,kind,title,lat,lon,payload,search_visibility,created_at,updated_at) \
         VALUES ($1,'Werkstatt',$2,54.9,8.3,$3::jsonb,'private',clock_timestamp(),clock_timestamp())",
    )
    .bind(NODE_ID)
    .bind(PRIVATE_TITLE)
    .bind(format!(
        r#"{{"summary":"Nur für den Eigentümer","created_by_account_id":"{OWNER_ID}"}}"#
    ))
    .execute(&pool)
    .await
    .expect("insert private node for worker race proof");

    let generation_spec = exact_generation_spec();
    let generation = generation_spec.generation_id.to_owned();
    let projection_worker = worker(pool.clone());
    projection_worker
        .start_generation(generation_spec)
        .await
        .expect("start generation for worker race proof");

    let mut version_blocker = pool.begin().await.expect("begin version blocker");
    sqlx::query("SELECT node_id FROM search_node_versions WHERE node_id=$1 FOR UPDATE")
        .bind(NODE_ID)
        .fetch_one(&mut *version_blocker)
        .await
        .expect("lock node version before worker");

    let worker_task = tokio::spawn(async move {
        projection_worker.claim_and_process_one().await
    });

    tokio::time::timeout(std::time::Duration::from_secs(10), async {
        loop {
            let waiting: bool = sqlx::query_scalar(
                "SELECT EXISTS (\
                   SELECT 1 FROM pg_stat_activity \
                   WHERE pid <> pg_backend_pid() \
                     AND datname = current_database() \
                     AND state = 'active' \
                     AND wait_event_type = 'Lock' \
                     AND query ILIKE '%INSERT INTO search_node_projections%'\
                 )",
            )
            .fetch_one(&pool)
            .await
            .expect("observe worker lock wait");
            if waiting {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(25)).await;
        }
    })
    .await
    .expect("worker did not reach version fence while holding owner lock");

    let mut disable_connection = pool
        .acquire()
        .await
        .expect("acquire account-disable connection");
    let mut disable_task = tokio::spawn(async move {
        sqlx::query("UPDATE domain_accounts SET disabled=TRUE WHERE id=$1")
            .bind(OWNER_ID)
            .execute(&mut *disable_connection)
            .await
    });
    assert!(
        tokio::time::timeout(
            std::time::Duration::from_millis(250),
            &mut disable_task,
        )
        .await
        .is_err(),
        "owner disable bypassed the real worker's account lock",
    );

    version_blocker
        .commit()
        .await
        .expect("release node version for worker");
    let worker_outcome = tokio::time::timeout(
        std::time::Duration::from_secs(10),
        worker_task,
    )
    .await
    .expect("worker remained blocked after version release")
    .expect("join real worker race proof")
    .expect("process private projection in race proof");
    assert_eq!(worker_outcome, ProcessOutcome::Processed);

    let disabled_result = disable_task
        .await
        .expect("join concurrent owner disable")
        .expect("disable owner after worker commit");
    assert_eq!(disabled_result.rows_affected(), 1);
    assert_redacted(&projection(&pool, &generation).await);
}
'''
test_path.write_text(test_text.rstrip() + proof + "\n", encoding="utf-8")
