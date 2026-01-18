import { writable } from "svelte/store";
import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";
import { isRecord } from "$lib/utils/guards";
import { demoAccounts } from "$lib/demo/demoData";

// Definiert die Struktur des Benutzer-Objekts.
interface User {
  loggedIn: boolean;
  role?: string;
  current_account_id?: string;
}

interface Account {
  id: string;
  [key: string]: unknown;
}

const STORAGE_KEY = "gewebe_auth_user";

// Erstellt einen Store, um den Authentifizierungsstatus zu speichern.
// ACHTUNG: Der Login basiert rein auf der Existenz der Account-ID (kein Passwort).
// NICHT FÜR PRODUKTIVBETRIEB MIT ECHTEN DATEN GEEIGNET.
const createAuthStore = () => {
  // Initialisiere State aus localStorage, falls im Browser verfügbar
  let initialUser: User = {
    loggedIn: false,
    role: undefined,
    current_account_id: undefined,
  };

  if (browser) {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);

        // Validation: Ensure we have a valid object and only restore safe fields
        if (isRecord(parsed) && typeof parsed.loggedIn === "boolean") {
          initialUser = {
            loggedIn: parsed.loggedIn,
            // Do NOT restore role from storage to prevent privilege escalation via localStorage tampering.
            // For this demo mock, we hardcode 'weber' if logged in, mirroring the login logic.
            role: parsed.loggedIn ? "weber" : undefined,
            current_account_id:
              typeof parsed.current_account_id === "string"
                ? parsed.current_account_id
                : undefined,
          };
        }
      }
    } catch (e) {
      console.warn("Auth restoration failed:", e);
    }
  }

  const { subscribe, set } = writable<User>(initialUser);

  return {
    subscribe,
    // Echte Login-Logik: Verifiziert, ob der Account existiert
    login: async (accountId: string) => {
      let isValid = false;

      // 1. Versuche API
      const apiUrl = env.PUBLIC_GEWEBE_API_BASE ?? "";

      try {
        // Fetch specific account by ID to ensure privacy (no full list download)
        const res = await fetch(`${apiUrl}/api/accounts/${accountId}`);
        if (res.ok) {
            isValid = true;
        }
      } catch (e) {
        console.warn("Login: API unavailable, falling back to local demo check", e);
      }

      // 2. Fallback: Check local demo data if API failed or didn't find it (and we are in a demo context)
      // Note: This fallback ensures the demo works without a backend, but strictly matches IDs.
      if (!isValid) {
         if (demoAccounts.some(a => a.id === accountId)) {
             console.log("Login: Verified against local demo data.");
             isValid = true;
         }
      }

      if (isValid) {
        const user: User = {
            loggedIn: true,
            role: "weber",
            current_account_id: accountId,
        };
        set(user);
        if (browser) {
            // Only persist safe fields, never the role
            const safeStorage = {
            loggedIn: true,
            current_account_id: accountId,
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(safeStorage));
        }
      } else {
          console.error(`Login failed: Account ${accountId} not found.`);
      }
    },
    // Logout Logic
    logout: () => {
      const user: User = {
        loggedIn: false,
        role: undefined,
        current_account_id: undefined,
      };
      set(user);
      if (browser) {
        localStorage.removeItem(STORAGE_KEY);
      }
    },
  };
};

export const authStore = createAuthStore();
