feat(auth): implement basic POST /auth/session/refresh

Implements the POST /auth/session/refresh endpoint as step 2 of Phase 2
in the Auth Roadmap.
The endpoint reads the current `weltgewebe_session` cookie, invalidates the
old session in the in-memory store, creates a new session for the same
account, and returns a new rotated cookie.

Includes comprehensive tests verifying:
- Successful session rotation (old cookie becomes invalid, new cookie gets
  all security flags: Secure, HttpOnly, SameSite=Lax).
- Rejection of missing/invalid cookies (401 SESSION_EXPIRED).
- Rejection of cross-origin requests via the global CSRF middleware (403).

Updates the `auth-status-matrix` to document the endpoint as `Teil`,
noting that the target contract (true persistence and explicit Access/Refresh
token split) is not yet fully covered.
