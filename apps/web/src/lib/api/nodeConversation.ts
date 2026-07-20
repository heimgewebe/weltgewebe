export interface NodeConversation {
  id: string;
  conversation_type: "node";
  node_id: string;
  visibility: "public";
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  author_account_id: string | null;
  author_title: string;
  content: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface MessagePage {
  items: ConversationMessage[];
  page: {
    limit: number;
    next_cursor: string | null;
    has_more: boolean;
  };
}

interface ErrorPayload {
  code?: unknown;
  message?: unknown;
  current?: unknown;
}

function canonicalUtcTimestamp(value: string): string {
  const match = value.match(
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$/,
  );
  if (!match) return value;
  return `${match[1]}.${(match[2] ?? "").padEnd(9, "0")}Z`;
}

export function compareApiTimestamps(left: string, right: string): number {
  return canonicalUtcTimestamp(left).localeCompare(
    canonicalUtcTimestamp(right),
  );
}

export class NodeConversationApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly current?: ConversationMessage,
  ) {
    super(message);
    this.name = "NodeConversationApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new NodeConversationApiError(
      response.status,
      typeof payload.code === "string" ? payload.code : "request_failed",
      typeof payload.message === "string"
        ? payload.message
        : `HTTP ${response.status}`,
      payload.current as ConversationMessage | undefined,
    );
  }
  return response.json() as Promise<T>;
}

export function getNodeConversation(
  nodeId: string,
  signal?: AbortSignal,
): Promise<NodeConversation> {
  return request<NodeConversation>(
    `/api/nodes/${encodeURIComponent(nodeId)}/conversation`,
    { signal },
  );
}

export function listConversationMessages(
  conversationId: string,
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<MessagePage> {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  return request<MessagePage>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
    { signal },
  );
}

export function createConversationMessage(
  conversationId: string,
  content: string,
  idempotencyKey: string,
): Promise<ConversationMessage> {
  return request<ConversationMessage>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ content }),
    },
  );
}

export function updateConversationMessage(
  conversationId: string,
  messageId: string,
  content: string,
  updatedAt: string,
): Promise<ConversationMessage> {
  return request<ConversationMessage>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    {
      method: "PATCH",
      headers: { "If-Match": `"${updatedAt}"` },
      body: JSON.stringify({ content }),
    },
  );
}

export function tombstoneConversationMessage(
  conversationId: string,
  messageId: string,
  updatedAt: string,
): Promise<ConversationMessage> {
  return request<ConversationMessage>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    {
      method: "DELETE",
      headers: { "If-Match": `"${updatedAt}"` },
    },
  );
}
