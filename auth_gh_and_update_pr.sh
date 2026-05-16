#!/bin/bash
# Attempt to update PR #1072 using GitHub's SSH key authentication via curl

set -e

REPO_OWNER="heimgewebe"
REPO_NAME="weltgewebe"
PR_NUMBER="1072"

echo "Attempting to authenticate with GitHub via SSH..."

# Test SSH connection to GitHub
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✅ SSH authentication successful"
else
    echo "Attempting SSH connection..."
    ssh -T git@github.com || true
fi

# Read updated body
BODY_FILE="/workspaces/weltgewebe/.PR-1072-UPDATED-BODY.txt"
if [[ ! -f "$BODY_FILE" ]]; then
    echo "❌ Missing file: $BODY_FILE"
    exit 1
fi

BODY=$(cat "$BODY_FILE")

echo ""
echo "PR #1072 Update Details:"
echo "  File: $BODY_FILE"
echo "  Size: $(wc -c < "$BODY_FILE") bytes"
echo "  Lines: $(wc -l < "$BODY_FILE") lines"
echo ""

# GitHub API requires a token. Without it, we cannot update via REST API.
# However, we can use gh CLI if it can access the SSH key.

echo "Checking if 'gh' can use SSH credentials..."
if command -v gh &> /dev/null; then
    echo "✅ 'gh' CLI found"
    
    # Try to get auth status (will fail if not authenticated)
    if gh auth status 2>&1 | grep -q "Logged in"; then
        echo "✅ gh is already authenticated"
        echo ""
        echo "Updating PR #1072..."
        gh pr edit "$PR_NUMBER" --body-file "$BODY_FILE" --repo "$REPO_OWNER/$REPO_NAME"
        echo "✅ PR #1072 description updated successfully"
        exit 0
    else
        echo "⚠️  gh is not authenticated"
        echo ""
        echo "Attempting to use gh with SSH forwarding..."
        
        # Try using SSH as transport
        GH_TOKEN="" gh pr edit "$PR_NUMBER" --body-file "$BODY_FILE" --repo "$REPO_OWNER/$REPO_NAME" 2>&1 || {
            echo "❌ gh CLI update failed (no authentication available)"
            exit 1
        }
    fi
else
    echo "❌ 'gh' CLI not found"
    exit 1
fi
