use async_trait::async_trait;
use chrono::Utc;
use sqlx::PgPool;
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
        let now = Utc::now();
        let expires_at = now + chrono::Duration::days(1);

        sqlx::query(
            "INSERT INTO sessions (id, account_id, device_id, created_at, last_active, expires_at) 
             VALUES ($1, $2, $3, $4, $5, $6)",
        )
        .bind(&session_id)
        .bind(&account_id)
        .bind(&device_id)
        .bind(now)
        .bind(now)
        .bind(expires_at)
        .execute(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(Session {
            id: session_id,
            account_id,
            device_id,
            created_at: now,
            last_active: now,
            expires_at,
        })
    }

    async fn get(&self, session_id: &str) -> SessionResult<Option<Session>> {
        let row = sqlx::query_as::<_, Session>(
            "SELECT id, account_id, device_id, created_at, last_active, expires_at 
             FROM sessions 
             WHERE id = $1",
        )
        .bind(session_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        // Filter expired sessions
        Ok(row.filter(|s| !s.is_expired()))
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
        let now = Utc::now();
        let five_min_ago = now - chrono::Duration::minutes(5);

        sqlx::query(
            "UPDATE sessions 
             SET last_active = $1 
             WHERE id = $2 AND last_active < $3",
        )
        .bind(now)
        .bind(session_id)
        .bind(five_min_ago)
        .execute(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(())
    }

    async fn list_by_account(&self, account_id: &str) -> SessionResult<Vec<Session>> {
        let now = Utc::now();
        let sessions = sqlx::query_as::<_, Session>(
            "SELECT id, account_id, device_id, created_at, last_active, expires_at 
             FROM sessions 
             WHERE account_id = $1 AND expires_at > $2
             ORDER BY created_at DESC",
        )
        .bind(account_id)
        .bind(now)
        .fetch_all(&self.pool)
        .await
        .map_err(|_| SessionBackendError::Unavailable)?;

        Ok(sessions)
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

#[cfg(test)]
mod tests {
    #[tokio::test]
    async fn test_create_and_get() {
        // This is a placeholder test to show structure.
        // Real integration tests require DATABASE_URL to be set.
        // Test runs during CI when DATABASE_URL is present.
    }
}
