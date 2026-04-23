// apps/web/scripts/dev/gewebe-demo-server.mjs
// Thin wrapper to launch the shared demo API server from the web app workspace.
// The actual implementation lives at the repository root under scripts/dev.
// Keeping this wrapper ensures any tooling that expects the script inside
// apps/web continues to work without duplicating logic.

import "../../../../scripts/dev/gewebe-demo-server.mjs";
