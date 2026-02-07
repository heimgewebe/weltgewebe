use crate::config::AppConfig;
use governor::{clock::DefaultClock, state::keyed::DefaultKeyedStateStore, Quota, RateLimiter};
use std::net::IpAddr;
use std::num::NonZeroU32;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum RateLimitError {
    #[error("Too many requests from IP")]
    IpLimited,
    #[error("Too many requests for this email")]
    EmailLimited,
}

type IpLimiter = RateLimiter<IpAddr, DefaultKeyedStateStore<IpAddr>, DefaultClock>;
type EmailLimiter = RateLimiter<String, DefaultKeyedStateStore<String>, DefaultClock>;

pub struct AuthRateLimiter {
    ip_limiter_min: Option<IpLimiter>,
    ip_limiter_hour: Option<IpLimiter>,
    email_limiter_min: Option<EmailLimiter>,
    email_limiter_hour: Option<EmailLimiter>,
}

impl AuthRateLimiter {
    pub fn new(config: &AppConfig) -> Self {
        let ip_limiter_min = config.auth_rl_ip_per_min.and_then(|limit| {
            NonZeroU32::new(limit).map(|l| RateLimiter::keyed(Quota::per_minute(l)))
        });

        let ip_limiter_hour = config.auth_rl_ip_per_hour.and_then(|limit| {
            NonZeroU32::new(limit).map(|l| RateLimiter::keyed(Quota::per_hour(l)))
        });

        let email_limiter_min = config.auth_rl_email_per_min.and_then(|limit| {
            NonZeroU32::new(limit).map(|l| RateLimiter::keyed(Quota::per_minute(l)))
        });

        let email_limiter_hour = config.auth_rl_email_per_hour.and_then(|limit| {
            NonZeroU32::new(limit).map(|l| RateLimiter::keyed(Quota::per_hour(l)))
        });

        Self {
            ip_limiter_min,
            ip_limiter_hour,
            email_limiter_min,
            email_limiter_hour,
        }
    }

    pub fn check(&self, ip: IpAddr, email_key: &str) -> Result<(), RateLimitError> {
        if let Some(limiter) = &self.ip_limiter_min {
            if limiter.check_key(&ip).is_err() {
                tracing::warn!(%ip, "Rate limit exceeded (IP/min)");
                return Err(RateLimitError::IpLimited);
            }
        }
        if let Some(limiter) = &self.ip_limiter_hour {
            if limiter.check_key(&ip).is_err() {
                tracing::warn!(%ip, "Rate limit exceeded (IP/hour)");
                return Err(RateLimitError::IpLimited);
            }
        }

        let email_key_owned = email_key.to_string();

        if let Some(limiter) = &self.email_limiter_min {
            if limiter.check_key(&email_key_owned).is_err() {
                tracing::warn!(email_hash = %email_key_owned, scope = "min", "Rate limit exceeded (Email)");
                return Err(RateLimitError::EmailLimited);
            }
        }
        if let Some(limiter) = &self.email_limiter_hour {
            if limiter.check_key(&email_key_owned).is_err() {
                tracing::warn!(email_hash = %email_key_owned, scope = "hour", "Rate limit exceeded (Email)");
                return Err(RateLimitError::EmailLimited);
            }
        }

        Ok(())
    }
}
