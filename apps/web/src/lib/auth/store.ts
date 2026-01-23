import { writable } from "svelte/store";
import { browser } from "$app/environment";
import { isRecord } from "$lib/utils/guards";

// Definiert die Struktur des Benutzer-Objekts passend zur API /auth/me
export interface AuthStatus {
  authenticated: boolean;
  account_id?: string;
  role: string;
}

const initialUser: AuthStatus = {
  authenticated: false,
  role: "gast",
  account_id: undefined,
};

const createAuthStore = () => {
  const store = writable<AuthStatus>(initialUser);
  const { subscribe, set } = store;

  // Helper to fetch current status
  const checkAuth = async () => {
    if (!browser) return initialUser;
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        // Validation: Ensure robust handling of API response
        if (
          isRecord(data) &&
          typeof data.authenticated === "boolean" &&
          typeof data.role === "string"
        ) {
          const validated: AuthStatus = {
            authenticated: data.authenticated,
            role: data.role,
            account_id:
              typeof data.account_id === "string" ? data.account_id : undefined,
          };
          set(validated);
          return validated;
        } else {
          console.warn("Invalid auth payload:", data);
        }
      }
      // Fallback
      set(initialUser);
      return initialUser;
    } catch (e) {
      console.warn("Auth check failed:", e);
      set(initialUser);
      return initialUser;
    }
  };

  return {
    subscribe,
    checkAuth,
    login: async (accountId: string) => {
      if (!browser) return;
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_id: accountId }),
          credentials: "include",
        });
        if (res.ok) {
          const newState = await checkAuth(); // Refresh state
          if (!newState.authenticated) {
            throw new Error(
              "Login appeared successful but session was not established (cookie issue?).",
            );
          }
        } else {
          console.error("Login failed:", res.status);
          throw new Error("Login failed");
        }
      } catch (e) {
        console.error("Login error:", e);
        throw e;
      }
    },
    logout: async () => {
      if (!browser) return;
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          credentials: "include",
        });
        set(initialUser);
      } catch (e) {
        console.error("Logout error:", e);
        // Even if network fails, we should clear local state
        set(initialUser);
      }
    },
  };
};

export const authStore = createAuthStore();

// Initialize in browser to restore session
if (browser) {
  authStore.checkAuth();
}
