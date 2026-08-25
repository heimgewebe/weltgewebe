import urllib.request
import json
import os

token = os.environ.get('GH_TOKEN')
if token:
    req = urllib.request.Request("https://api.github.com/repos/heimgewebe/weltgewebe/issues/1794/comments")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            comments = json.loads(response.read().decode())
            for c in comments:
                print(f"[{c['user']['login']}] {c['body']}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("GH_TOKEN not set")
