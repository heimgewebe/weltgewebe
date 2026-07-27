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
    controller = requestController;
    publish({ ...previous, state: "checking" });

    pending = (async () => {
      try {
        const response = await fetcher("/api/auth/me", {
          credentials: "include",
          signal: requestController.signal,
        });
        if (current !== revision) return get(store);
        if (response.status === 401 || response.status === 403) {
          return publish(anonymous(), true);
        }
        if (!response.ok) {
          return publish({ ...previous, state: "degraded" });
        }

        const data = (await response.json()) as Partial<AuthStatus>;
        if (
          data?.authenticated === true &&
          typeof data.role === "string" &&
          typeof data.account_id === "string"
        ) {
          return publish(
            {
              state: "authenticated",
              authenticated: true,
              role: data.role,
              account_id: data.account_id,
            },
            true,
          );
        }
        return publish({ ...previous, state: "degraded" });
      } catch (error) {
        if (current !== revision) return get(store);
        if ((error as { name?: string })?.name === "AbortError") {
          return publish(previous);
        }
        return publish({ ...previous, state: "degraded" });
      } finally {
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
      const response = await fetcher("/api/auth/dev/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: accountId }),
        credentials: "include",
      });
      if (!response.ok) throw new Error("Login failed");
      const next = await checkAuth({ force: true });
      if (!next.authenticated) {
        throw new Error("Login succeeded but no session was established.");
      }
    },
    requestLogin: async (email: string) => {
      if (!isBrowser) return;
      const response = await fetcher("/api/auth/magic-link/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
        credentials: "include",
      });
      if (!response.ok) {
        if (response.status === 404 || response.status === 403) {
          throw new Error("Public login is disabled.");
        }
        throw new Error(`Request failed: ${response.status}`);
      }
    },
    logout: async () => {
      if (!isBrowser) return;
      clearSensitiveSession(isBrowser);
      try {
        const response = await fetcher("/api/auth/logout", {
          method: "POST",
          credentials: "include",
        });
        if (
          !response.ok &&
          response.status !== 401 &&
          response.status !== 403
        ) {
          throw new Error(`Logout failed: ${response.status}`);
        }
        await checkAuth({ force: true });
      } catch (error) {
        console.error("Logout error:", error);
        publish(anonymous(), true);
      }
    },
  };
};

export const authStore = createAuthStore();

if (browser) void authStore.checkAuth();
