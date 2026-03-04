"""Check PR status"""
import requests

TOKEN = "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"
OWNER = "nomanqadri34"
REPO = "smart-health-system"

headers = {"Authorization": f"Bearer {TOKEN}"}
url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls?state=all&per_page=100"

response = requests.get(url, headers=headers)
if response.status_code == 200:
    prs = response.json()
    print(f"Total PRs: {len(prs)}")
    print("\nRecent PRs:")
    for pr in prs[:10]:
        status = "MERGED" if pr['merged_at'] else "OPEN" if pr['state'] == 'open' else "CLOSED"
        print(f"  PR #{pr['number']}: {pr['title']} [{status}]")
