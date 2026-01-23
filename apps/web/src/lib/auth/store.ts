import { writable } from "svelte/store";
import { browser } from "$app/environment";

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
  const { subscribe, set } = writable<AuthStatus>(initialUser);

  // Helper to fetch current status
  const checkAuth = async () => {
    if (!browser) return;
    try {
      const res = await fetch("/api/auth/me");
      if (res.ok) {
        const data: AuthStatus = await res.json();
        set(data);
      } else {
        // Fallback or error handling
        set(initialUser);
      }
    } catch (e) {
      console.warn("Auth check failed:", e);
      set(initialUser);
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
        });
        if (res.ok) {
          await checkAuth(); // Refresh state
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
        await fetch("/api/auth/logout", { method: "POST" });
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
