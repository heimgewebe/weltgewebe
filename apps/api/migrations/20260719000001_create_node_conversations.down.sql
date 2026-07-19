DROP TRIGGER IF EXISTS domain_nodes_create_conversation ON domain_nodes;
DROP FUNCTION IF EXISTS weltgewebe_create_node_conversation();

DROP TRIGGER IF EXISTS domain_messages_outbox ON domain_messages;
DROP TRIGGER IF EXISTS domain_conversations_outbox ON domain_conversations;

DELETE FROM domain_outbox
WHERE aggregate_type IN ('conversation', 'message');

DROP TABLE IF EXISTS domain_messages;
DROP TABLE IF EXISTS domain_conversations;
DROP FUNCTION IF EXISTS weltgewebe_enqueue_conversation_event();
DROP FUNCTION IF EXISTS weltgewebe_node_conversation_id(TEXT);
