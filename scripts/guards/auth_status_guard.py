import json
import os
import sys

def main():
    matrix_md = 'docs/reports/auth-status-matrix.md'
    matrix_json = 'docs/reports/auth-status-matrix.json'

    if not os.path.exists(matrix_md):
        print(f"Error: Required file {matrix_md} is missing.")
        sys.exit(1)

    if not os.path.exists(matrix_json):
        print(f"Error: Required file {matrix_json} is missing.")
        sys.exit(1)

    with open(matrix_json, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {matrix_json} is not valid JSON.")
            sys.exit(1)

    areas = data.get('areas', {})
    required_areas = [
        'magic_link', 'session', 'session_refresh', 'logout',
        'logout_all', 'devices', 'step_up_auth', 'passkeys',
        'security_invariants'
    ]

    for area in required_areas:
        if area not in areas:
            print(f"Error: Required area '{area}' is missing from JSON.")
            sys.exit(1)

    with open(matrix_md, 'r') as f:
        md_content = f.read()

    # Check for references to Alt-/Ist-Linie (legacy base)
    if 'docs/adr/ADR-0005-auth.md' not in md_content or 'docs/specs/auth-blueprint.md' not in md_content:
        print("Error: Matrix must explicitly reference ADR-0005 and auth-blueprint as Alt-/Ist-Linie.")
        sys.exit(1)

    # Check for references to Ziel-/Soll-Linie
    ziel_docs = [
        'docs/adr/ADR-0006__auth-magic-link-session-passkey.md',
        'docs/specs/auth-api.md',
        'docs/specs/auth-state-machine.md',
        'docs/specs/auth-ui.md'
    ]
    for doc in ziel_docs:
        if doc not in md_content:
            print(f"Error: Matrix must explicitly reference {doc} as Ziel-/Soll-Linie.")
            sys.exit(1)

    # Check that /me/email is marked as open
    if '/me/email' not in md_content or 'Offen' not in md_content[md_content.find('/me/email'):]:
        print("Error: /me/email must be explicitly marked as 'Offen' in the matrix.")
        sys.exit(1)

    print("✅ Auth Status Guard passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
