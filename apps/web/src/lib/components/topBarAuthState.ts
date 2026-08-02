import type { AuthStatus } from "$lib/auth/store";

export interface TopBarAuthView {
  showAccountLink: boolean;
  showLoginLink: boolean;
  showRetry: boolean;
  retryLabel: string;
  isGuest: boolean;
}

export function deriveTopBarAuthView(auth: AuthStatus): TopBarAuthView {
  const showRetry = auth.state === "checking" || auth.state === "degraded";
  return {
    showAccountLink: auth.authenticated,
    showLoginLink: !auth.authenticated && auth.state === "unauthenticated",
    showRetry,
    retryLabel:
      auth.state === "checking"
        ? "Prüfe Anmeldung …"
        : "Verbindung erneut prüfen",
    isGuest: auth.authenticated && auth.role === "gast",
  };
}
