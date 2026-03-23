import re

with open("apps/api/tests/api_auth.rs", "r") as f:
    text = f.read()

# We need to remove `let _guard_cookie = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_COOKIE_SECURE", "1");`
# from tests that DO NOT have `"Secure"`.

matches = re.finditer(r"(async fn ([\w_]+)\(\).*?\{(.*?)\n\})", text, re.DOTALL)
for m in matches:
    full_block = m.group(1)
    name = m.group(2)
    body = m.group(3)

    has_guard = 'weltgewebe_api::test_helpers::EnvGuard::set("AUTH_COOKIE_SECURE", "1")' in body
    has_assert = '"Secure"' in body

    if has_guard and not has_assert:
        # We need to replace the guard in this specific block
        cleaned_block = re.sub(
            r'\s*let _guard_cookie = weltgewebe_api::test_helpers::EnvGuard::set\("AUTH_COOKIE_SECURE", "1"\);\n',
            '\n',
            full_block
        )
        text = text.replace(full_block, cleaned_block)

with open("apps/api/tests/api_auth.rs", "w") as f:
    f.write(text)
