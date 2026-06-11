import re
pattern = r'(?:^|[;&|()]\s*)(?:(?:time|env)\s+)?(?:[a-zA-Z_][a-zA-Z0-9_]*=(?:\S+|"[^"]*"|\'[^\']*\')\s+)*cargo\s+test\b'

cases = [
    ("cargo test --locked", True),
    ("DATABASE_URL=\"postgres://...\" cargo test --locked", True),
    ("echo prepare && cargo test --locked", True),
    ("echo \"cargo test\"", False),
    ("printf '%s\n' \"cargo test\"", False),
    ("time cargo test", True),
    ("env FOO=bar cargo test", True),
    ("FOO=cargo test", False),
    ("echo cargo test", False),
    ("DATABASE_URL='foo' cargo test", True),
    ("DATABASE_URL=foo cargo test", True),
    ("FOO=1 BAR=2 cargo test", True),
]

for cmd, expected in cases:
    res = bool(re.search(pattern, cmd))
    if res != expected:
        print(f"FAILED: {cmd} -> got {res}, expected {expected}")
print("Done")
