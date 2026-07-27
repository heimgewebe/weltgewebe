import { get, writable } from "svelte/store";
import { browser } from "$app/environment";

export type AuthState =
  | "checking"
  | "authenticated"
  | "unauthenticated"
  | "degraded";
export interface AuthStatus {
  state: AuthState;
  authenticated: boolean;
  account_id?: string;
  role: string;
}

export interface AuthCheckOptions {
  force?: boolean;
}

export interface AuthStoreOptions {
  isBrowser?: boolean;
  fetcher?: typeof fetch;
  authCheckTimeoutMs?: number;
}

const anonymous = (state: AuthState = "unauthenticated"): AuthStatus => ({
  state,
  authenticated: false,
  role: "gast",
});

const SENSITIVE_SESSION_PREFIXES = [
  "weltgewebe:garnrolle-draft:",
  "weltgewebe:garnrolle-return-location:",
] as const;

function clearSensitiveSession(enabled: boolean, keepAccountId?: string) {
  if (!enabled || typeof sessionStorage === "undefined") return;
  const remove: string[] = [];
  for (let index = 0; index < sessionStorage.length; index += 1) {
    const key = sessionStorage.key(index);
    if (!key) continue;
    const prefix = SENSITIVE_SESSION_PREFIXES.find((value) =>
      key.startsWith(value),
    );
    if (prefix && key !== (keepAccountId ? `${prefix}${keepAccountId}` : "")) {
      remove.push(key);
    }
  }
  remove.forEach((key) => sessionStorage.removeItem(key));
}

export const createAuthStore = (options: AuthStoreOptions = {}) => {
  const isBrowser = options.isBrowser ?? browser;
  const fetcher = options.fetcher ?? fetch;
  const authCheckTimeoutMs = Math.max(1, options.authCheckTimeoutMs ?? 5000);
  const store = writable<AuthStatus>(
    anonymous(isBrowser ? "checking" : "unauthenticated"),
  );
  const { subscribe, set } = store;
  let revision = 0;
  let controller: AbortController | undefined;
  let pending: Promise<AuthStatus> | undefined;

  const publish = (next: AuthStatus, authoritative = false): AuthStatus => {
    if (authoritative) {
      clearSensitiveSession(
        isBrowser,
        next.authenticated ? next.account_id : undefined,
      );
    }
    set(next);
    return next;
  };

  const checkAuth = (options: AuthCheckOptions = {}): Promise<AuthStatus> => {
    if (!isBrowser) return Promise.resolve(get(store));
    if (pending && !options.force) return pending;
    if (pending) {
      revision += 1;
      controller?.abort();
      pending = undefined;
    }

    const previous = get(store);
    const current = ++revision;
    const requestController = new AbortController();
    const timeout = setTimeout(
      () => requestController.abort(),
      authCheckTimeoutMs,
    );
    controller = requestController;
    publish({ ...previous, state: "checking" });

    pending = (async () => {
      try {
        const next = await (
          await import("./check")
        ).fetchAuthStatus(fetcher, requestController.signal);
        if (current !== revision) return get(store);
        return next
          ? publish(next, true)
          : publish({ ...previous, state: "degraded" });
      } catch {
        if (current !== revision) return get(store);
        return publish({ ...previous, state: "degraded" });
      } finally {
        clearTimeout(timeout);
        if (current === revision) {
          controller = undefined;
          pending = undefined;
        }
      }
    })();
    return pending;
  };

  return {
    subscribe,
    checkAuth,
    devLogin: async (accountId: string) => {
      if (!isBrowser) return;
      await (await import("./actions")).devLogin(fetcher, accountId);
      const next = await checkAuth({ force: true });
      if (!next.authenticated) {
        throw new Error("Login succeeded but no session was established.");
      }
    },
    requestLogin: async (email: string) => {
      if (!isBrowser) return;
      await (await import("./actions")).requestLogin(fetcher, email);
    },
    logout: async () => {
      if (!isBrowser) return;
      const previous = get(store);
      try {
        await (await import("./actions")).endSession(fetcher);
        const verified = await checkAuth({ force: true });
        if (verified.state !== "unauthenticated") {
          throw new Error("Logout could not be verified.");
        }
      } catch (error) {
        publish({ ...previous, state: "degraded" });
        throw error;
      }
    },
  };
};

export const authStore = createAuthStore();

if (browser) void authStore.checkAuth();
