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
  author_account_id: string;
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

export function getNodeConversation(nodeId: string): Promise<NodeConversation> {
  return request<NodeConversation>(
    `/api/nodes/${encodeURIComponent(nodeId)}/conversation`,
  );
}

export function listConversationMessages(
  conversationId: string,
  cursor?: string | null,
): Promise<MessagePage> {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  return request<MessagePage>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
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
