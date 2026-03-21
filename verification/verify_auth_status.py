import os
import sys

def check_file_exists(filepath, description):
    if os.path.exists(filepath):
        print(f"✅ [OK] {description} found at {filepath}")
        return True
    else:
        print(f"❌ [FAIL] {description} NOT found at {filepath}")
        return False

def check_file_contains(filepath, search_string, description):
    if not os.path.exists(filepath):
        print(f"❌ [FAIL] {filepath} NOT found for {description} check.")
        return False

    with open(filepath, 'r') as f:
        content = f.read()
        if search_string in content:
            print(f"✅ [OK] {description} found in {filepath}")
            return True
        else:
            print(f"❌ [FAIL] {description} NOT found in {filepath}")
            return False

def main():
    print("--- Verifying Auth Architecture Status ---")
    all_passed = True

    # 1. Login UI exists
    if not check_file_exists("apps/web/src/routes/login/+page.svelte", "Login UI"):
        all_passed = False

    # 2. verify_magic_link.py exists
    if not check_file_exists("verification/verify_magic_link.py", "Magic Link Verification Script"):
        all_passed = False

    # 3. Runbook contains public magic-link config
    if not check_file_contains("docs/runbook.md", "AUTH_PUBLIC_LOGIN", "Public Magic-Link Configuration (AUTH_PUBLIC_LOGIN)"):
        all_passed = False

    # 4. Matrix and JSON exist
    if not check_file_exists("docs/reports/auth-status-matrix.md", "Auth Status Matrix Markdown"):
        all_passed = False
    if not check_file_exists("docs/reports/auth-status-matrix.json", "Auth Status Matrix JSON"):
        all_passed = False

    print("------------------------------------------")
    if all_passed:
        print("✅ Verifications passed.")
        sys.exit(0)
    else:
        print("❌ Verifications failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
