import { writable } from "svelte/store";

// Definiert die Struktur des Benutzer-Objekts.
interface User {
  loggedIn: boolean;
  role?: string;
  current_account_id?: string;
}

// Erstellt einen Store, um den Authentifizierungsstatus zu speichern.
// Dieser Store ist ein Platzhalter und wird später durch eine echte
// Session-Management-Logik ersetzt.
// NICHT FÜR PRODUKTIVBETRIEB – nur Demo.
const createAuthStore = () => {
  const { subscribe, set } = writable<User>({
    loggedIn: false,
    role: undefined,
    current_account_id: undefined,
  });

  return {
    subscribe,
    // Platzhalter-Funktion für den Login
    // Requires accountId; injected for testing convenience
    login: (accountId: string) => {
      // TODO: Echte Login-Logik implementieren
      set({
        loggedIn: true,
        role: "weber",
        current_account_id: accountId,
      });
    },
    // Platzhalter-Funktion für den Logout
    logout: () => {
      // TODO: Echte Logout-Logik implementieren
      set({
        loggedIn: false,
        role: undefined,
        current_account_id: undefined,
      });
    },
  };
};

export const authStore = createAuthStore();
