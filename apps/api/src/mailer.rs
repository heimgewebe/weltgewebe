use crate::config::AppConfig;
use anyhow::{Context, Result};
use lettre::{
    message::header::ContentType, transport::smtp::authentication::Credentials, AsyncSmtpTransport,
    AsyncTransport, Message, Tokio1Executor,
};

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

        self.transport.send(email).await.context("failed to send email")?;
        Ok(())
    }
}
