use axum::{body::Body, http::Request, middleware::Next, response::Response};

/// Platzhalter-Middleware für die Authentifizierung.
///
/// Diese Middleware ist aktuell nur ein Platzhalter und lässt alle Anfragen unverändert
/// durch. Sie dient als Einhängepunkt für die zukünftige Implementierung der
/// echten Authentifizierungs- und Autorisierungslogik.
///
/// In Zukunft wird diese Funktion:
/// - Den Session-Token aus dem Cookie extrahieren.
/// - Die Session serverseitig validieren.
/// - Den Benutzerkontext in die Anfrage einfügen (z.B. als Extension).
/// - Anfragen ohne gültige Session abweisen (z.B. mit HTTP 401 Unauthorized).
pub async fn require_auth(request: Request<Body>, next: Next) -> Response {
    // Aktuell wird die Anfrage einfach durchgelassen.
    tracing::warn!("Authentifizierung ist noch nicht implementiert – Zugriff erlaubt!");
    next.run(request).await
}
