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
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;
    use tempfile::NamedTempFile;

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn mailer_fails_with_invalid_from_address() {
        let file = NamedTempFile::new().unwrap();
        std::fs::write(file.path(), YAML).unwrap();

        // Valid SMTP host/port to pass builder construction until From parsing
        let _host = EnvGuard::set("SMTP_HOST", "127.0.0.1");
        let _port = EnvGuard::set("SMTP_PORT", "1025");
        let _user = EnvGuard::set("SMTP_USER", "user");
        let _pass = EnvGuard::set("SMTP_PASS", "pass");

        // Invalid From Address
        let _from = EnvGuard::set("SMTP_FROM", "not-an-email");

        let config = AppConfig::load_from_path(file.path()).unwrap();

        // This should fail because "not-an-email" cannot be parsed into a Mailbox
        // The Mailer::new implementation parses `from` immediately.
        let res = Mailer::new(&config);
        assert!(res.is_err());
        assert!(res
            .unwrap_err()
            .to_string()
            .contains("invalid from address"));
    }
}
