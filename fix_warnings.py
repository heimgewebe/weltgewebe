from pathlib import Path

content = Path("apps/api/src/auth/session.rs").read_text()
content = content.replace("let s1 = store.create(\"acc-1\".to_string(), Some(\"dev-A\".to_string()));", "let _s1 = store.create(\"acc-1\".to_string(), Some(\"dev-A\".to_string()));")
content = content.replace("let s2 = store.create(\"acc-1\".to_string(), Some(\"dev-A\".to_string()));", "let _s2 = store.create(\"acc-1\".to_string(), Some(\"dev-A\".to_string()));")

Path("apps/api/src/auth/session.rs").write_text(content)
