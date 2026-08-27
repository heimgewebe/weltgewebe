-- Moving the canonical browser origin from https://weltgewebe.net to
-- https://commonthing.net makes existing PushSubscription objects unreachable
-- from the new origin. Retire every subscription that is active at cutover so
-- the redirect-only legacy origin cannot leave server-side zombie deliveries.
--
-- Keep the exact retirement set and timestamp as a rollback marker. New
-- commonThing subscriptions created after this migration are not recorded here.
CREATE TABLE web_push_origin_cutover_retirements (
    subscription_id UUID        PRIMARY KEY
                                REFERENCES web_push_subscriptions (id) ON DELETE CASCADE,
    retired_at      TIMESTAMPTZ NOT NULL
);

INSERT INTO web_push_origin_cutover_retirements (subscription_id, retired_at)
SELECT id, NOW()
FROM web_push_subscriptions
WHERE disabled_at IS NULL;

UPDATE web_push_deliveries AS delivery
SET status = 'gone',
    claimed_until = NULL,
    last_error = 'retired by commonThing origin cutover'
FROM web_push_origin_cutover_retirements AS retirement
WHERE delivery.subscription_id = retirement.subscription_id
  AND delivery.status IN ('pending', 'retry', 'sending');

UPDATE web_push_subscriptions AS subscription
SET disabled_at = retirement.retired_at,
    updated_at = NOW(),
    last_error = 'retired by commonThing origin cutover'
FROM web_push_origin_cutover_retirements AS retirement
WHERE subscription.id = retirement.subscription_id
  AND subscription.disabled_at IS NULL;
