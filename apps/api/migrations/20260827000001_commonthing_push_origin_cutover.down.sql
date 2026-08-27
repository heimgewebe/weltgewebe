-- Re-enable only rows that are still disabled by the exact cutover timestamp.
-- A subscription that was re-registered or disabled again after the cutover is
-- deliberately left untouched. Historical deliveries stay terminal instead of
-- being replayed during rollback.
UPDATE web_push_subscriptions AS subscription
SET disabled_at = NULL,
    updated_at = NOW(),
    last_error = NULL
FROM web_push_origin_cutover_retirements AS retirement
WHERE subscription.id = retirement.subscription_id
  AND subscription.disabled_at = retirement.retired_at;

DROP TABLE web_push_origin_cutover_retirements;
