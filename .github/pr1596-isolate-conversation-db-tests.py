from pathlib import Path

path = Path("apps/api/tests/db_node_conversations.rs")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    "use std::{path::PathBuf, str::FromStr, sync::Arc};",
    "use std::{ops::Deref, path::PathBuf, str::FromStr, sync::Arc};",
    "Deref import",
)

old_pool = '''async fn pool() -> sqlx::PgPool {
    let options = PgConnectOptions::from_str(&direct_database_url()).expect("valid DATABASE_URL");
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect_with(options)
        .await
        .expect("connect PostgreSQL");
    let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    sqlx::migrate::Migrator::new(migrations)
        .await
        .expect("load migrations")
        .run(&pool)
        .await
        .expect("run migrations");
    pool
}
'''
new_pool = '''struct IsolatedTestDatabase {
    pool: sqlx::PgPool,
    admin_pool: sqlx::PgPool,
    schema: String,
}

impl Deref for IsolatedTestDatabase {
    type Target = sqlx::PgPool;

    fn deref(&self) -> &Self::Target {
        &self.pool
    }
}

impl IsolatedTestDatabase {
    async fn cleanup(self) {
        let Self {
            pool,
            admin_pool,
            schema,
        } = self;
        pool.close().await;
        sqlx::query(&format!("DROP SCHEMA {schema} CASCADE"))
            .execute(&admin_pool)
            .await
            .expect("drop isolated conversation proof schema");
        admin_pool.close().await;
    }
}

async fn pool() -> IsolatedTestDatabase {
    let options = PgConnectOptions::from_str(&direct_database_url()).expect("valid DATABASE_URL");
    let admin_pool = PgPoolOptions::new()
        .max_connections(1)
        .connect_with(options.clone())
        .await
        .expect("connect PostgreSQL for isolated schema management");
    let schema = format!(
        "pr1596_conversations_{}",
        uuid::Uuid::new_v4().simple()
    );
    sqlx::query(&format!("CREATE SCHEMA {schema}"))
        .execute(&admin_pool)
        .await
        .expect("create isolated conversation proof schema");

    let connection_schema = schema.clone();
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .after_connect(move |connection, _metadata| {
            let schema = connection_schema.clone();
            Box::pin(async move {
                sqlx::query(&format!("SET search_path TO {schema}, public"))
                    .execute(connection)
                    .await?;
                Ok(())
            })
        })
        .connect_with(options)
        .await
        .expect("connect PostgreSQL in isolated conversation proof schema");
    let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    sqlx::migrate::Migrator::new(migrations)
        .await
        .expect("load migrations")
        .run(&pool)
        .await
        .expect("run migrations in isolated conversation proof schema");
    IsolatedTestDatabase {
        pool,
        admin_pool,
        schema,
    }
}
'''
replace_once(old_pool, new_pool, "isolated pool")

count = text.count("    pool.close().await;\n")
if count != 2:
    raise SystemExit(f"cleanup calls: expected 2 occurrences, found {count}")
text = text.replace("    pool.close().await;\n", "    pool.cleanup().await;\n")

path.write_text(text, encoding="utf-8")
