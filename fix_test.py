from pathlib import Path
content = Path("apps/api/tests/api_auth.rs").read_text()

# Fix the format macro strings
content = content.replace("Request::delete(&format!(\"/auth/devices/{}\", device_b_id))", "Request::delete(format!(\"/auth/devices/{}\", device_b_id))")
content = content.replace("Request::delete(&format!(\"/auth/devices/{}\", device_a_id))", "Request::delete(format!(\"/auth/devices/{}\", device_a_id))")

Path("apps/api/tests/api_auth.rs").write_text(content)
