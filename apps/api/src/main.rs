use weltgewebe_api::run;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    run().await
}
