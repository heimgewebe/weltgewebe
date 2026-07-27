import { isRecord } from "$lib/utils/guards";
import type { AuthStatus } from "./store";

export async function fetchAuthStatus(
  fetcher: typeof fetch,
  signal: AbortSignal,
): Promise<AuthStatus | null> {
  const response = await fetcher("/api/auth/me", {
    credentials: "include",
    signal,
  });
  const value: unknown = await response.json().catch(() => null);
  if (!isRecord(value) || typeof value.role !== "string") return null;

  let status: AuthStatus | null = null;
  if (
    value.authenticated === true &&
    typeof value.account_id === "string" &&
    value.account_id
  ) {
    status = {
      state: "authenticated",
      authenticated: true,
      account_id: value.account_id,
      role: value.role,
    };
  } else if (
    value.authenticated === false &&
    value.role === "gast" &&
    value.account_id == null
  ) {
    status = {
      state: "unauthenticated",
      authenticated: false,
      role: "gast",
    };
  }
  return status &&
    (response.ok || (response.status === 401 && !status.authenticated))
    ? status
    : null;
}
