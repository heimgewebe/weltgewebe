import { writable } from "svelte/store";

// Definiert die Struktur des Benutzer-Objekts.
interface User {
  loggedIn: boolean;
  role?: string;
}

// Erstellt einen Store, um den Authentifizierungsstatus zu speichern.
// Dieser Store ist ein Platzhalter und wird später durch eine echte
// Session-Management-Logik ersetzt.
const createAuthStore = () => {
  const { subscribe, set } = writable<User>({
    loggedIn: false,
    role: undefined,
  });

  return {
    subscribe,
    // Platzhalter-Funktion für den Login
    login: () => {
      console.log("Platzhalter: login() aufgerufen");
      set({ loggedIn: true, role: "weber" });
    },
    // Platzhalter-Funktion für den Logout
    logout: () => {
      console.log("Platzhalter: logout() aufgerufen");
      set({ loggedIn: false, role: undefined });
    },
  };
};

export const authStore = createAuthStore();
