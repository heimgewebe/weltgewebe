use std::fmt;

pub fn readiness_check_failed(component: &str, error: &(impl fmt::Display + ?Sized)) {
    tracing::warn!(error = %error, %component, "{component} health check failed");
}

pub fn readiness_checks_succeeded() {
    tracing::info!("all readiness checks passed");
}
