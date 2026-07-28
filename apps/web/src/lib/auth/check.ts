import { isRecord } from "$lib/utils/guards";
import type { AuthRole, AuthStatus } from "./store";

const AUTHENTICATED_ROLES = new Set<AuthRole>(["weber", "admin"]);

function isAuthenticatedRole(value: unknown): value is "weber" | "admin" {
  return (
    typeof value === "string" && AUTHENTICATED_ROLES.has(value as AuthRole)
  );
}

export async function fetchAuthStatus(
  fetcher: typeof fetch,
  signal: AbortSignal,
): Promise<AuthStatus | null> {
  const response = await fetcher("/api/auth/me", {
    credentials: "include",
    signal,
  });
  const value: unknown = await response.json().catch(() => null);
  if (!isRecord(value)) return null;

  let status: AuthStatus | null = null;
  if (
    value.authenticated === true &&
    typeof value.account_id === "string" &&
    value.account_id.length > 0 &&
    isAuthenticatedRole(value.role)
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
