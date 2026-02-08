use crate::config::AppConfig;
use anyhow::{Context, Result};
use lettre::{
    message::header::ContentType, transport::smtp::authentication::Credentials, AsyncSmtpTransport,
    AsyncTransport, Message, Tokio1Executor,
};

#[derive(Debug)]
pub struct Mailer {
    transport: AsyncSmtpTransport<Tokio1Executor>,
    from: String,
}

impl Mailer {
    pub fn new(config: &AppConfig) -> Result<Self> {
        let host = config.smtp_host.as_deref().context("SMTP_HOST missing")?;
        let port = config.smtp_port.unwrap_or(587);
        let user = config.smtp_user.as_deref().context("SMTP_USER missing")?;
        let pass = config.smtp_pass.as_deref().context("SMTP_PASS missing")?;
        let from = config.smtp_from.clone().context("SMTP_FROM missing")?;

        let creds = Credentials::new(user.to_string(), pass.to_string());

        // Validate from address format early
        if from.parse::<lettre::message::Mailbox>().is_err() {
            anyhow::bail!("invalid from address: {}", from);
        }

        // Use relay builder
        let transport = AsyncSmtpTransport::<Tokio1Executor>::relay(host)
            .context("failed to build SMTP relay")?
            .port(port)
            .credentials(creds)
            .build();

        Ok(Self { transport, from })
    }

    pub async fn send_magic_link(&self, to: &str, link: &str) -> Result<()> {
        let email = Message::builder()
            .from(self.from.parse().context("invalid from address")?)
            .to(to.parse().context("invalid to address")?)
            .subject("Log in to Weltgewebe")
            .header(ContentType::TEXT_HTML)
            .body(format!(
                r#"<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; padding: 20px;">
    <h2>Log in to Weltgewebe</h2>
    <p>Click the link below to sign in:</p>
    <p style="margin: 20px 0;">
        <a href="{}" style="background-color: #0070f3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Sign In</a>
    </p>
    <p style="color: #666; font-size: 0.9em;">This link expires soon.</p>
    <p style="color: #666; font-size: 0.9em;">If you did not request this email, you can safely ignore it.</p>
</body>
</html>"#,
                link
            ))
            .context("failed to build email")?;

        self.transport
            .send(email)
            .await
            .context("failed to send email")?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::AppConfig;
    use serial_test::serial;

    #[test]
    #[serial]
    fn mailer_fails_with_invalid_from_address() {
        // Construct AppConfig manually to avoid dependency on config validation logic
        let config = AppConfig {
            fade_days: 7,
            ron_days: 84,
            anonymize_opt_in: true,
            delegation_expire_days: 28,
            auth_public_login: false,
            app_base_url: None,
            auth_trusted_proxies: None,
            auth_allow_emails: None,
            auth_allow_email_domains: None,
            auth_auto_provision: false,
            auth_rl_ip_per_min: None,
            auth_rl_ip_per_hour: None,
            auth_rl_email_per_min: None,
            auth_rl_email_per_hour: None,
            smtp_host: Some("127.0.0.1".to_string()),
            smtp_port: Some(1025),
            smtp_user: Some("user".to_string()),
            smtp_pass: Some("pass".to_string()),
            smtp_from: Some("not-an-email".to_string()),
            auth_log_magic_token: false,
        };

        // This should fail because "not-an-email" cannot be parsed into a Mailbox
        let res = Mailer::new(&config);
        assert!(res.is_err());
        assert!(res
            .unwrap_err()
            .to_string()
            .contains("invalid from address"));
    }
}
