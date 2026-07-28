import type {
  ArchivedNodeConversation,
  ConversationMessage,
} from "./nodeConversation";

export interface ArchivedConversationView {
  conversation: ArchivedNodeConversation;
  messages: ConversationMessage[];
}

const MAX_MESSAGE_PAGES = 200;

interface ErrorPayload {
  code?: unknown;
  message?: unknown;
}

export class ArchiveConversationApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ArchiveConversationApiError";
  }
}

function malformedResponse(): never {
  throw new ArchiveConversationApiError(
    502,
    "malformed_response",
    "the conversation archive response is malformed",
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(value) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isBoundedString(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  if (typeof value !== "string") return false;
  const length = Array.from(value).length;
  return length >= minimum && length <= maximum;
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)
  );
}

function parseArchivedConversation(
  value: unknown,
  expectedId: string,
): ArchivedNodeConversation {
  if (
    !isRecord(value) ||
    value.id !== expectedId ||
    value.conversation_type !== "node" ||
    value.lifecycle_state !== "archived" ||
    value.node_id !== null ||
    typeof value.node_id_snapshot !== "string" ||
    value.node_id_snapshot.length === 0 ||
    !isBoundedString(value.node_title_snapshot, 1, 200) ||
    value.visibility !== "public" ||
    !isTimestamp(value.created_at) ||
    !isTimestamp(value.updated_at) ||
    !isTimestamp(value.archived_at) ||
    value.deleted_at !== null
  ) {
    malformedResponse();
  }
  return value as unknown as ArchivedNodeConversation;
}

function parseMessage(
  value: unknown,
  conversationId: string,
): ConversationMessage {
  if (
    !isRecord(value) ||
    !isUuid(value.id) ||
    value.conversation_id !== conversationId ||
    !(
      value.author_account_id === null ||
      typeof value.author_account_id === "string"
    ) ||
    !isBoundedString(value.author_title, 1, 200) ||
    !isTimestamp(value.created_at) ||
    !isTimestamp(value.updated_at) ||
    !(value.deleted_at === null || isTimestamp(value.deleted_at)) ||
    !(
      (value.deleted_at === null && isBoundedString(value.content, 1, 4_000)) ||
      (value.deleted_at !== null && value.content === null)
    )
  ) {
    malformedResponse();
  }
  return value as unknown as ConversationMessage;
}

function canonicalUtcTimestamp(value: string): string {
  const match = value.match(
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$/,
  );
  if (!match) return value;
  return `${match[1]}.${(match[2] ?? "").padEnd(9, "0")}Z`;
}

function compareTimestamps(left: string, right: string): number {
  return canonicalUtcTimestamp(left).localeCompare(
    canonicalUtcTimestamp(right),
  );
}

function parseMessagePage(
  value: unknown,
  conversationId: string,
): {
  items: ConversationMessage[];
  nextCursor: string | null;
  hasMore: boolean;
} {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !isRecord(value.page) ||
    !Number.isInteger(value.page.limit) ||
    (value.page.limit as number) < 1 ||
    (value.page.limit as number) > 50 ||
    value.items.length > (value.page.limit as number) ||
    typeof value.page.has_more !== "boolean" ||
    !(
      (value.page.has_more === true &&
        isBoundedString(value.page.next_cursor, 1, 2_000)) ||
      (value.page.has_more === false && value.page.next_cursor === null)
    )
  ) {
    malformedResponse();
  }

  return {
    items: value.items.map((item) => parseMessage(item, conversationId)),
    nextCursor: value.page.next_cursor as string | null,
    hasMore: value.page.has_more,
  };
}

async function request(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { credentials: "include", signal });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new ArchiveConversationApiError(
      response.status,
      typeof payload.code === "string" ? payload.code : "request_failed",
      typeof payload.message === "string"
        ? payload.message
        : `HTTP ${response.status}`,
    );
  }
  try {
    return await response.json();
  } catch (error) {
    if (error instanceof SyntaxError) malformedResponse();
    throw error;
  }
}

export async function loadArchivedConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ArchivedConversationView> {
  const conversation = parseArchivedConversation(
    await request(
      `/api/conversations/${encodeURIComponent(conversationId)}`,
      signal,
    ),
    conversationId,
  );
  const messages: ConversationMessage[] = [];
  const messageIds = new Set<string>();
  const cursors = new Set<string>();
  let cursor: string | null = null;
  let hasMore = true;
  let pageCount = 0;

  while (hasMore) {
    pageCount += 1;
    if (pageCount > MAX_MESSAGE_PAGES) malformedResponse();
    const query = new URLSearchParams({ limit: "50" });
    if (cursor) query.set("cursor", cursor);
    const page = parseMessagePage(
      await request(
        `/api/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
        signal,
      ),
      conversationId,
    );
    for (const message of page.items) {
      if (messageIds.has(message.id)) malformedResponse();
      messageIds.add(message.id);
    }
    messages.unshift(...page.items);

    hasMore = page.hasMore;
    if (!hasMore) break;
    if (!page.nextCursor || cursors.has(page.nextCursor)) malformedResponse();
    cursors.add(page.nextCursor);
    cursor = page.nextCursor;
  }

  messages.sort(
    (left, right) =>
      compareTimestamps(left.created_at, right.created_at) ||
      left.id.localeCompare(right.id),
  );
  return { conversation, messages };
}
