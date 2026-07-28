import type { AuthStatus } from "./store";

export async function devLogin(
  fetcher: typeof fetch,
  accountId: string,
): Promise<void> {
  const response = await fetcher("/api/auth/dev/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: accountId }),
    credentials: "include",
  });
  if (!response.ok) throw new Error("Login failed");
}

export async function requestLogin(
  fetcher: typeof fetch,
  email: string,
): Promise<void> {
  const response = await fetcher("/api/auth/magic-link/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    credentials: "include",
  });
  if (response.ok) return;
  if (response.status === 404 || response.status === 403) {
    throw new Error("Public login is disabled.");
  }
  throw new Error(`Request failed: ${response.status}`);
}

export async function endSession(fetcher: typeof fetch): Promise<void> {
  const response = await fetcher("/api/auth/logout", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Logout failed: ${response.status}`);
}

export async function logoutAndVerify(
  fetcher: typeof fetch,
  previous: AuthStatus,
  ownedRevision: number,
  currentRevision: () => number,
  publishDegraded: (previous: AuthStatus) => void,
  verify: () => Promise<AuthStatus>,
): Promise<void> {
  try {
    await endSession(fetcher);
    const verified = await verify();
    if (verified.state !== "unauthenticated") {
      throw new Error("Logout unverified");
    }
  } catch (error) {
    if (ownedRevision === currentRevision()) publishDegraded(previous);
    throw error;
  }
}
