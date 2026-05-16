#!/usr/bin/env python3
"""
ONE-CLICK PR #1072 DESCRIPTION UPDATE

This script provides a one-click way to update PR #1072 description.
Run this and follow the link.
"""

import json
import subprocess
from pathlib import Path

def get_pr_body():
    """Read the updated PR body from file."""
    body_file = Path("/workspaces/weltgewebe/.PR-1072-UPDATED-BODY.txt")
    if not body_file.exists():
        print("ERROR: .PR-1072-UPDATED-BODY.txt not found")
        return None
    return body_file.read_text()

def update_via_github_ui():
    """Generate clickable link for GitHub UI manual update."""
    body = get_pr_body()
    if not body:
        return
    
    # URL to the PR
    pr_url = "https://github.com/heimgewebe/weltgewebe/pull/1072"
    
    print("\n" + "="*70)
    print("ONE-CLICK PR #1072 DESCRIPTION UPDATE")
    print("="*70)
    print()
    print("OPTION 1: Manual Update (Easiest, No Token Needed)")
    print("-" * 70)
    print(f"1. Open: {pr_url}")
    print("2. Click the '...' (three dots) in top-right of PR description")
    print("3. Click 'Edit'")
    print("4. Replace all text with this (copy to clipboard):")
    print()
    print("-" * 70)
    print(body)
    print("-" * 70)
    print()
    print("5. Click 'Save'")
    print()
    print("OR copy this command to get the text:")
    print()
    print("  cat /workspaces/weltgewebe/.PR-1072-UPDATED-BODY.txt | xclip -selection clipboard")
    print()
    print("="*70)
    print()

def update_via_token():
    """Provide token-based update instructions."""
    print("\nOPTION 2: Automated Update (Requires GitHub Token)")
    print("-" * 70)
    print()
    print("1. Generate a token at: https://github.com/settings/tokens/new")
    print("   (Requires 'repo' scope)")
    print()
    print("2. Run:")
    print()
    print("   export GH_TOKEN='ghp_your_token_here'")
    print("   cd /workspaces/weltgewebe")
    print("   ./update_pr_1072_body.sh")
    print()
    print("="*70)
    print()

if __name__ == "__main__":
    update_via_github_ui()
    update_via_token()
    
    print("\nBoth options are ready. Choose one and follow the steps.")
    print("\nPR #1072: https://github.com/heimgewebe/weltgewebe/pull/1072")
