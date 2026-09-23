import os
import re
import json
import urllib.request

from datetime import datetime

def update_stats():
    token = os.environ.get("GITHUB_TOKEN", "")
    username = os.environ.get("GITHUB_USERNAME", "basith-ahamad-dev")
    svg_path = "dist/github-stats.svg"

    if not os.path.exists(svg_path):
        print(f"SVG file {svg_path} not found.")
        return

    current_year = datetime.now().year
    from_date = f"{current_year}-01-01T00:00:00Z"
    to_date = f"{current_year}-12-31T23:59:59Z"

    query = f"""query {{
      viewer {{
        thisYear: contributionsCollection(from: "{from_date}", to: "{to_date}") {{
          contributionCalendar {{
            totalContributions
          }}
        }}
        rollingYear: contributionsCollection {{
          contributionCalendar {{
            totalContributions
          }}
        }}
      }}
      user(login: "{username}") {{
        thisYear: contributionsCollection(from: "{from_date}", to: "{to_date}") {{
          contributionCalendar {{
            totalContributions
          }}
        }}
        rollingYear: contributionsCollection {{
          contributionCalendar {{
            totalContributions
          }}
        }}
      }}
    }}"""

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query}).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            viewer_data = data.get("data", {}).get("viewer") or {}
            user_data = data.get("data", {}).get("user") or {}

            candidates = [
                viewer_data.get("thisYear", {}).get("contributionCalendar", {}).get("totalContributions"),
                viewer_data.get("rollingYear", {}).get("contributionCalendar", {}).get("totalContributions"),
                user_data.get("thisYear", {}).get("contributionCalendar", {}).get("totalContributions"),
                user_data.get("rollingYear", {}).get("contributionCalendar", {}).get("totalContributions"),
            ]
            valid_candidates = [c for c in candidates if c is not None and c > 0]
            count = max(valid_candidates) if valid_candidates else None

            print(f"Candidates from viewer & user: {candidates}")
            print(f"Selected total contributions: {count}")
            
            if count is not None:
                print(f"Fetched real total contributions from GitHub API: {count}")
                with open(svg_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Update the SVG numbers
                content = re.sub(r'(data-testid="commits"\s*>\s*)\d+(\s*</text>)', rf'\g<1>{count}\g<2>', content)
                content = re.sub(r'Total Commits\s*:\s*\d+', f'Total Commits: {count}', content)
                content = re.sub(r'Total Commits\s*\(last year\)\s*:\s*\d+', f'Total Commits: {count}', content)

                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Successfully updated {svg_path} with {count} commits.")
            else:
                print("Could not retrieve totalContributions from GraphQL response.")
    except Exception as e:
        print(f"Error fetching contributions: {e}")

if __name__ == "__main__":
    update_stats()
