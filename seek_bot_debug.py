import os
import requests
from bs4 import BeautifulSoup
import json
import re

# --- TEST ONE SEARCH ONLY ---
keyword = "business analyst"
location = "Brisbane"
search_term = keyword.replace(" ", "-")
url = f"https://www.seek.com.au/{search_term}-jobs/in-{location}"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

print(f"Fetching: {url}")
response = requests.get(url, headers=headers, timeout=15)
print(f"Status code: {response.status_code}")
print(f"Response length: {len(response.text)} characters")

soup = BeautifulSoup(response.text, "html.parser")

# Check what tags exist
print(f"\nArticle tags found: {len(soup.find_all('article'))}")
print(f"Script tags found: {len(soup.find_all('script'))}")

# Check for JSON-LD
ld_scripts = soup.find_all("script", {"type": "application/ld+json"})
print(f"JSON-LD scripts found: {len(ld_scripts)}")
for i, s in enumerate(ld_scripts):
    print(f"  Script {i}: {s.string[:200] if s.string else 'empty'}")

# Check for data-automation attributes
auto_tags = soup.find_all(attrs={"data-automation": True})
print(f"\ndata-automation tags found: {len(auto_tags)}")
for tag in auto_tags[:10]:
    print(f"  {tag.get('data-automation')} — {tag.name}")

# Check page scripts for job data
scripts = soup.find_all("script")
for i, script in enumerate(scripts):
    if script.string and any(word in script.string for word in ["jobTitle", "JobPosting", "job-card", "jobId"]):
        print(f"\nScript {i} contains job-related data:")
        print(script.string[:500])
        break

# Save raw HTML for inspection
with open("/mnt/user-data/outputs/seek_page.html", "w") as f:
    f.write(response.text)
print("\nRaw HTML saved to seek_page.html")
