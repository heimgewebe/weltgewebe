import { writable } from "svelte/store";

// Definiert die Struktur des Benutzer-Objekts.
interface User {
  loggedIn: boolean;
  role?: string;
}

// Erstellt einen Store, um den Authentifizierungsstatus zu speichern.
// Dieser Store ist ein Platzhalter und wird später durch eine echte
// Session-Management-Logik ersetzt.
// NICHT FÜR PRODUKTIVBETRIEB – nur Demo.
const createAuthStore = () => {
  const { subscribe, set } = writable<User>({
    loggedIn: false,
    role: undefined,
  });

  return {
    subscribe,
    // Platzhalter-Funktion für den Login
    login: () => {
      // TODO: Echte Login-Logik implementieren
      set({ loggedIn: true, role: "weber" });
    },
    // Platzhalter-Funktion für den Logout
    logout: () => {
      // TODO: Echte Logout-Logik implementieren
      set({ loggedIn: false, role: undefined });
    },
  };
};

export const authStore = createAuthStore();
