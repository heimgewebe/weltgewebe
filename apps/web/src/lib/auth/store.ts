import { writable } from "svelte/store";
import { browser } from "$app/environment";
import { isRecord } from "$lib/utils/guards";

// Definiert die Struktur des Benutzer-Objekts.
interface User {
  loggedIn: boolean;
  role?: string;
  current_account_id?: string;
}

const STORAGE_KEY = "gewebe_auth_user";

// Erstellt einen Store, um den Authentifizierungsstatus zu speichern.
// Dieser Store ist ein Platzhalter und wird später durch eine echte
// Session-Management-Logik ersetzt.
// NICHT FÜR PRODUKTIVBETRIEB – nur Demo.
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
    // Platzhalter-Funktion für den Login
    // Requires accountId; injected for testing convenience
    login: (accountId: string) => {
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
    },
    // Platzhalter-Funktion für den Logout
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
