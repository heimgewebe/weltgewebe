import re

with open("apps/api/tests/api_auth.rs", "r") as f:
    text = f.read()

matches = re.finditer(r"async fn ([\w_]+)\(\).*?\{(.*?)\n\}", text, re.DOTALL)
found_guards = []
for m in matches:
    name = m.group(1)
    body = m.group(2)
    has_guard = "AUTH_COOKIE_SECURE" in body
    has_assert = '"Secure"' in body
    if has_guard or has_assert:
        found_guards.append((name, has_guard, has_assert))

for name, guard, ast in found_guards:
    print(f"Test: {name} | Has Guard: {guard} | Has Assert: {ast}")
