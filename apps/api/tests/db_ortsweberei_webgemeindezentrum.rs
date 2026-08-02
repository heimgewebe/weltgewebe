//! PostgreSQL proof for the first executable Ortsweberei / Gewebezelle /
//! Webgemeindezentrum slice.
//!
//! This test deliberately exercises the database contract, not only Rust
//! structs: the stable one-to-one topology, truth-preserving location state,
//! stable center identity, and append-only location history must survive any
//! future write path that talks directly to PostgreSQL.

mod support;

use std::path::PathBuf;

use serial_test::serial;
use sqlx::{Executor, PgPool, Row};

const CELL_ID: &str = "hamm.weltgewebe.net";
const ORTSWEBEREI_ID: &str = "ortsweberei-hamm";
const CENTER_ID: &str = "webgemeindezentrum-hammer-park";

async fn pool() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point at a direct disposable PostgreSQL database");
    support::postgres_proof::assert_direct_disposable_database_url(&url);
    let pool = PgPool::connect(&url).await.expect("connect to PostgreSQL");
    let migrations_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("load migrations");
    migrator.run(&pool).await.expect("run migrations");
    pool
}

#[tokio::test]
#[ignore = "requires direct disposable PostgreSQL"]
#[serial]
async fn canonical_center_is_stable_truthful_one_to_one_and_append_only() {
    let pool = pool().await;

    let row = sqlx::query(
        "SELECT o.id AS ortsweberei_id, o.slug, o.name AS ortsweberei_name,
                o.gewebezelle_id, o.active_webgemeindezentrum_id,
                g.lifecycle_state AS cell_state,
                c.id AS center_id, c.name AS center_name, c.location_state,
                c.lat, c.lon, c.location_label, c.meeting_note, c.access_note
         FROM ortswebereien o
         JOIN gewebezellen g ON g.id = o.gewebezelle_id
         JOIN webgemeindezentren c
           ON c.id = o.active_webgemeindezentrum_id
          AND c.ortsweberei_id = o.id
         WHERE o.id = $1",
    )
    .bind(ORTSWEBEREI_ID)
    .fetch_one(&pool)
    .await
    .expect("read canonical Ortsweberei topology");

    assert_eq!(row.get::<String, _>("ortsweberei_id"), ORTSWEBEREI_ID);
    assert_eq!(row.get::<String, _>("slug"), "hamm");
    assert_eq!(row.get::<String, _>("ortsweberei_name"), "Ortsweberei Hamm");
    assert_eq!(row.get::<String, _>("gewebezelle_id"), CELL_ID);
    assert_eq!(
        row.get::<String, _>("active_webgemeindezentrum_id"),
        CENTER_ID
    );
    assert_eq!(row.get::<String, _>("cell_state"), "active");
    assert_eq!(row.get::<String, _>("center_id"), CENTER_ID);
    assert_eq!(
        row.get::<String, _>("center_name"),
        "Webgemeindezentrum Hammer Park"
    );
    assert_eq!(row.get::<String, _>("location_state"), "desired");
    assert!((row.get::<f64, _>("lat") - 53.5585).abs() < 1e-9);
    assert!((row.get::<f64, _>("lon") - 10.0580).abs() < 1e-9);
    assert_eq!(
        row.get::<String, _>("location_label"),
        "Hammer Park – gewünschter Treffpunkt auf der Grünfläche"
    );
    assert!(
        row.get::<String, _>("meeting_note")
            .contains("tatsächlich zusammenkommen"),
        "meeting note must explain why this real place was chosen"
    );
    assert!(
        row.get::<String, _>("access_note")
            .contains("noch nicht bestätigt"),
        "desired placement must not claim permission, accessibility or availability"
    );

    let initial_history = sqlx::query(
        "SELECT event_type, location_state, lat, lon, location_label, reason
         FROM webgemeindezentrum_location_history
         WHERE webgemeindezentrum_id = $1
         ORDER BY event_id",
    )
    .bind(CENTER_ID)
    .fetch_all(&pool)
    .await
    .expect("read initial location history");
    assert_eq!(initial_history.len(), 1);
    assert_eq!(
        initial_history[0].get::<String, _>("event_type"),
        "placement_desired"
    );
    assert_eq!(
        initial_history[0].get::<String, _>("location_state"),
        "desired"
    );
    assert!((initial_history[0].get::<f64, _>("lat") - 53.5585).abs() < 1e-9);
    assert!((initial_history[0].get::<f64, _>("lon") - 10.0580).abs() < 1e-9);
    assert!(initial_history[0]
        .get::<String, _>("reason")
        .contains("gewünschter gemeinsamer Treffpunkt"));

    // A single Ortsweberei cannot silently acquire a second center.
    let duplicate_center = sqlx::query(
        "INSERT INTO webgemeindezentren (
             id, ortsweberei_id, name, location_state, lat, lon,
             location_label, meeting_note, access_note, created_at, updated_at
         ) VALUES (
             'proof-second-center', $1, 'Zweites Zentrum', 'desired', 53.56, 10.06,
             'Nicht zulässig', 'Nicht zulässig', 'Nicht bestätigt', NOW(), NOW()
         )",
    )
    .bind(ORTSWEBEREI_ID)
    .execute(&pool)
    .await;
    assert!(
        duplicate_center.is_err(),
        "one Ortsweberei must have exactly one center row"
    );

    // A stable cell cannot be assigned to two different Ortswebereien.
    let duplicate_cell_binding = sqlx::query(
        "INSERT INTO ortswebereien (
             id, slug, name, description, gewebezelle_id, lifecycle_state,
             active_webgemeindezentrum_id, created_at, updated_at
         ) VALUES (
             'proof-duplicate-cell-ortsweberei', 'proof-duplicate-cell',
             'Unzulässige Ortsweberei', 'Unzulässige Doppelbindung', $1, 'active',
             'proof-never-created-center', NOW(), NOW()
         )",
    )
    .bind(CELL_ID)
    .execute(&pool)
    .await;
    assert!(
        duplicate_cell_binding.is_err(),
        "one Gewebezelle must not be shared by two Ortswebereien"
    );

    // Create a second valid topology, then try an atomic center swap. The
    // active-center ids stay globally unique, so only the same-Ortsweberei
    // composite foreign key can reject the cross-binding at commit time.
    let mut topology_tx = pool.begin().await.expect("begin second topology");
    topology_tx
        .execute(
            "INSERT INTO gewebezellen (id, lifecycle_state, created_at, updated_at)
             VALUES ('proof.weltgewebe.net', 'active', NOW(), NOW())",
        )
        .await
        .expect("insert proof cell");
    topology_tx
        .execute(
            "INSERT INTO ortswebereien (
                 id, slug, name, description, gewebezelle_id, lifecycle_state,
                 active_webgemeindezentrum_id, created_at, updated_at
             ) VALUES (
                 'proof-ortsweberei', 'proof', 'Proof Ortsweberei',
                 'Second valid topology', 'proof.weltgewebe.net', 'active',
                 'proof-center', NOW(), NOW()
             )",
        )
        .await
        .expect("insert proof Ortsweberei");
    topology_tx
        .execute(
            "INSERT INTO webgemeindezentren (
                 id, ortsweberei_id, name, location_state, lat, lon,
                 location_label, meeting_note, access_note, created_at, updated_at
             ) VALUES (
                 'proof-center', 'proof-ortsweberei', 'Proof Zentrum',
                 'desired', 53.50, 10.00, 'Proof place', 'Proof meeting',
                 'Not confirmed', NOW(), NOW()
             )",
        )
        .await
        .expect("insert proof center");
    topology_tx
        .commit()
        .await
        .expect("commit valid second topology");

    let mut cross_binding = pool.begin().await.expect("begin cross-binding proof");
    sqlx::query(
        "UPDATE ortswebereien
         SET active_webgemeindezentrum_id = CASE id
             WHEN $1 THEN 'proof-center'
             WHEN 'proof-ortsweberei' THEN $2
         END,
         updated_at = NOW()
         WHERE id IN ($1, 'proof-ortsweberei')",
    )
    .bind(ORTSWEBEREI_ID)
    .bind(CENTER_ID)
    .execute(&mut *cross_binding)
    .await
    .expect("deferred same-parent constraint permits statement until commit");
    assert!(
        cross_binding.commit().await.is_err(),
        "active center must belong to the same Ortsweberei even in an atomic swap"
    );

    // Moving the desired placement preserves the stable center id and appends
    // a new event instead of rewriting the original decision.
    sqlx::query(
        "UPDATE webgemeindezentren
         SET location_state = 'provisional',
             lat = 53.5586,
             lon = 10.0581,
             location_label = 'Hammer Park – vorläufig präzisierter Treffpunkt',
             updated_at = '2026-08-03T10:08:00Z'
         WHERE id = $1",
    )
    .bind(CENTER_ID)
    .execute(&pool)
    .await
    .expect("update center location");

    let stable_id: String =
        sqlx::query_scalar("SELECT id FROM webgemeindezentren WHERE ortsweberei_id = $1")
            .bind(ORTSWEBEREI_ID)
            .fetch_one(&pool)
            .await
            .expect("read stable center id after move");
    assert_eq!(stable_id, CENTER_ID, "a move must not mint a new center id");

    let history = sqlx::query(
        "SELECT event_id, event_type, location_state, lat, lon, location_label
         FROM webgemeindezentrum_location_history
         WHERE webgemeindezentrum_id = $1
         ORDER BY event_id",
    )
    .bind(CENTER_ID)
    .fetch_all(&pool)
    .await
    .expect("read appended history");
    assert_eq!(history.len(), 2);
    assert_eq!(
        history[0].get::<String, _>("event_type"),
        "placement_desired"
    );
    assert_eq!(
        history[1].get::<String, _>("event_type"),
        "placement_provisional"
    );
    assert_eq!(history[1].get::<String, _>("location_state"), "provisional");
    assert!((history[1].get::<f64, _>("lat") - 53.5586).abs() < 1e-9);
    assert!((history[1].get::<f64, _>("lon") - 10.0581).abs() < 1e-9);
    assert_eq!(
        history[1].get::<String, _>("location_label"),
        "Hammer Park – vorläufig präzisierter Treffpunkt"
    );

    sqlx::query(
        "UPDATE webgemeindezentren
         SET lat = 53.5587,
             lon = 10.0582,
             location_label = 'Hammer Park – verschobener vorläufiger Treffpunkt',
             updated_at = '2026-08-04T10:08:00Z'
         WHERE id = $1",
    )
    .bind(CENTER_ID)
    .execute(&pool)
    .await
    .expect("move center without changing its evidence state");
    let moved_event_type: String = sqlx::query_scalar(
        "SELECT event_type
         FROM webgemeindezentrum_location_history
         WHERE webgemeindezentrum_id = $1
         ORDER BY event_id DESC
         LIMIT 1",
    )
    .bind(CENTER_ID)
    .fetch_one(&pool)
    .await
    .expect("read pure move event");
    assert_eq!(moved_event_type, "moved");

    assert!(
        sqlx::query(
            "UPDATE webgemeindezentren
             SET lat = 53.5588,
                 updated_at = '2026-08-03T00:00:00Z'
             WHERE id = $1",
        )
        .bind(CENTER_ID)
        .execute(&pool)
        .await
        .is_err(),
        "location history must reject backdated mutations"
    );

    let first_event_id = history[0].get::<i64, _>("event_id");
    assert!(
        sqlx::query(
            "UPDATE webgemeindezentrum_location_history
             SET reason = 'rewritten' WHERE event_id = $1",
        )
        .bind(first_event_id)
        .execute(&pool)
        .await
        .is_err(),
        "location history must reject rewrites"
    );
    assert!(
        sqlx::query("DELETE FROM webgemeindezentrum_location_history WHERE event_id = $1")
            .bind(first_event_id)
            .execute(&pool)
            .await
            .is_err(),
        "location history must reject deletion"
    );

    assert!(
        sqlx::query("UPDATE webgemeindezentren SET location_state = 'reserved' WHERE id = $1")
            .bind(CENTER_ID)
            .execute(&pool)
            .await
            .is_err(),
        "unknown or overclaiming location states must be rejected"
    );
    assert!(
        sqlx::query("UPDATE webgemeindezentren SET lat = 123.0 WHERE id = $1")
            .bind(CENTER_ID)
            .execute(&pool)
            .await
            .is_err(),
        "invalid coordinates must be rejected"
    );

    pool.close().await;
}
