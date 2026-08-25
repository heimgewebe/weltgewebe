# The CI failed because the PR body did not contain the required risk marker
# 'PR body must contain exactly one risk marker: <!-- weltgewebe-risk: R0|R1|R2|R3 -->'
# Wait, this is a GitHub Actions check that verifies pull request bodies and reviews.
# The tool 'submit' probably just created the PR, but I need to include the risk marker in the PR body.
# Let's amend the submit to include it, or we might need to amend the PR directly if we can't submit again.
