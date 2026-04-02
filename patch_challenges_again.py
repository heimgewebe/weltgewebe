import sys

with open("apps/api/src/auth/challenges.rs", "r", encoding="utf-8") as f:
    content = f.read()

target = """pub enum ChallengeIntent {
    LogoutAll,
    RemoveDevice { target_device_id: String },
}"""

replacement = """pub enum ChallengeIntent {
    LogoutAll,
    RemoveDevice { target_device_id: String },
    UpdateEmail { new_email: String },
}"""

if target in content:
    content = content.replace(target, replacement)
    with open("apps/api/src/auth/challenges.rs", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched apps/api/src/auth/challenges.rs successfully.")
else:
    print("Target string not found in apps/api/src/auth/challenges.rs.")
    sys.exit(1)
