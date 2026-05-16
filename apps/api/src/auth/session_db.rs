use async_trait::async_trait;
use sqlx::{postgres::PgRow, PgPool, Row};
use uuid::Uuid;

use super::session::{Session, SessionBackendError, SessionOps, SessionResult};

/// Database-backed session store for direct PostgreSQL persistence.
/// Sessions created here survive across server restarts.
#[derive(Clone)]
pub struct DbSessionStore {
    pool: PgPool,
}

impl DbSessionStore {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    fn session_from_row(row: PgRow) -> Result<Session, sqlx::Error> {
        Ok(Session {
            id: row.try_get("id")?,
            account_id: row.try_get("account_id")?,
            device_id: row.try_get("device_id")?,
            created_at: row.try_get("created_at")?,
            last_active: row.try_get("last_active")?,
            expires_at: row.try_get("expires_at")?,
        })
    }
}

#[async_trait]
impl SessionOps for DbSessionStore {
    async fn create(
        &self,
        account_id: String,
        existing_device_id: Option<String>,
    ) -> SessionResult<Session> {
        let session_id = Uuid::new_v4().to_string();
        let device_id = existing_device_id.unwrap_or_else(|| Uuid::new_v4().to_string());
        let row = sqlx::query(
            "INSERT INTO sessions (id, account_id, device_id, created_at, last_active, expires_at)
             VALUES ($1, $2, $3, NOW(), NOW(), NOW() + INTERVAL '1 day')
             RETURNING id, account_id, device_id, created_at, last_active, expires_at",
        )
        .bind(&session_id)
        .bind(&account_id)
        .bind(&device_id)
        .fetch_one(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Self::session_from_row(row).map_err(|_| SessionBackendError::Unavailable)
    }

    async fn get(&self, session_id: &str) -> SessionResult<Option<Session>> {
        let row = sqlx::query(
            "SELECT id, account_id, device_id, created_at, last_active, expires_at
             FROM sessions
             WHERE id = $1",
        )
        .bind(session_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        let session = row
            .map(Self::session_from_row)
            .transpose()
            .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(session.filter(|s| !s.is_expired()))
    }

    async fn delete(&self, session_id: &str) -> SessionResult<()> {
        sqlx::query("DELETE FROM sessions WHERE id = $1")
            .bind(session_id)
            .execute(&self.pool)
            .await
            .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(())
    }

    async fn touch(&self, session_id: &str) -> SessionResult<()> {
        sqlx::query(
            "UPDATE sessions
             SET last_active = NOW()
             WHERE id = $1 AND last_active < NOW() - INTERVAL '5 minutes'",
        )
        .bind(session_id)
        .execute(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(())
    }

    async fn list_by_account(&self, account_id: &str) -> SessionResult<Vec<Session>> {
        let rows = sqlx::query(
            "SELECT id, account_id, device_id, created_at, last_active, expires_at
             FROM sessions
             WHERE account_id = $1 AND expires_at > NOW()
             ORDER BY created_at DESC",
        )
        .bind(account_id)
        .fetch_all(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        rows.into_iter()
            .map(Self::session_from_row)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| SessionBackendError::Unavailable)
    }

    async fn delete_by_device(&self, account_id: &str, device_id: &str) -> SessionResult<()> {
        sqlx::query(
            "DELETE FROM sessions 
             WHERE account_id = $1 AND device_id = $2",
        )
        .bind(account_id)
        .bind(device_id)
        .execute(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(())
    }

    async fn delete_all_by_account(&self, account_id: &str) -> SessionResult<()> {
        sqlx::query("DELETE FROM sessions WHERE account_id = $1")
            .bind(account_id)
            .execute(&self.pool)
            .await
            .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(())
    }
}
