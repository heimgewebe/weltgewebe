import json

with open("docs/reports/auth-status-matrix.json", "r") as f:
    data = json.load(f)
    print(data['areas']['session_refresh']['ist'])
    print(data['areas']['session_refresh']['status'])

print("---")
import re
with open("docs/reports/auth-status-matrix.md", "r") as f:
    text = f.read()

match = re.search(r"### 2.3 Session Refresh.*?(\*\*Ist:\*\*.*?)\n.*?\*\*Status:\*\* (.*?)\n", text, re.DOTALL)
if match:
    print(match.group(1))
    print(match.group(2))
