import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup
import json
import re

# --- CONFIG ---
SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]   # stored in GitHub Secrets
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]   # stored in GitHub Secrets
MAX_JOBS = 2                                   # number of jobs per search

# --- SEARCH COMBINATIONS ---
SEARCHES = [
    {"keyword": "business analyst", "location": "Brisbane"},
    {"keyword": "business analyst", "location": "Sydney"},
    {"keyword": "business analyst", "location": "Melbourne"},
    {"keyword": "business analyst", "location": "Adelaide"},
    {"keyword": "senior business analyst", "location": "Brisbane"},
    {"keyword": "senior business analyst", "location": "Sydney"},
    {"keyword": "senior business analyst", "location": "Melbourne"},
    {"keyword": "senior business analyst", "location": "Adelaide"},
]

# --- SCRAPE SEEK ---
def scrape_seek_jobs(keyword, location):
    search_term = keyword.replace(" ", "-")
    url = f"https://www.seek.com.au/{search_term}-jobs/in-{location}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        print(f"Request failed for {keyword} in {location}: {e}")
        return []

    if response.status_code != 200:
        print(f"Failed to fetch Seek page for {keyword} in {location}. Status: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    # Method 1 — Try extracting from embedded JSON (most reliable)
    try:
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "JobPosting":
                        title = item.get("title", "No title")
                        company = item.get("hiringOrganization", {}).get("name", "No company")
                        job_location = item.get("jobLocation", {}).get("address", {}).get("addressLocality", "")
                        link = item.get("url", "")
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "link": link
                        })
                        if len(jobs) >= MAX_JOBS:
                            return jobs
            elif isinstance(data, dict) and data.get("@type") == "JobPosting":
                title = data.get("title", "No title")
                company = data.get("hiringOrganization", {}).get("name", "No company")
                job_location = data.get("jobLocation", {}).get("address", {}).get("addressLocality", "")
                link = data.get("url", "")
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": job_location,
                    "link": link
                })
                if len(jobs) >= MAX_JOBS:
                    return jobs
    except Exception as e:
        print(f"JSON extraction failed: {e}")

    # Method 2 — Try data-automation attributes
    if not jobs:
        try:
            job_cards = soup.find_all("article")
            for card in job_cards[:MAX_JOBS]:
                title_tag = (
                    card.find("a", {"data-automation": "jobTitle"}) or
                    card.find("h3") or
                    card.find("h2")
                )
                company_tag = (
                    card.find("a", {"data-automation": "jobCompany"}) or
                    card.find("span", {"data-automation": "jobCompany"})
                )
                location_tag = (
                    card.find("span", {"data-automation": "jobCardLocation"}) or
                    card.find("span", {"data-automation": "jobLocation"})
                )
                link_tag = card.find("a", href=True)

                title = title_tag.text.strip() if title_tag else "No title"
                company = company_tag.text.strip() if company_tag else "No company"
                job_location = location_tag.text.strip() if location_tag else ""
                link = "https://www.seek.com.au" + link_tag["href"] if link_tag and link_tag["href"].startswith("/") else ""

                if title != "No title":
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "link": link
                    })
        except Exception as e:
            print(f"Article tag extraction failed: {e}")

    # Method 3 — Try finding job data in page scripts
    if not jobs:
        try:
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "jobTitle" in script.string:
                    matches = re.findall(r'"jobTitle":"([^"]+)".*?"advertiserName":"([^"]+)".*?"id":"(\d+)"', script.string)
                    for match in matches[:MAX_JOBS]:
                        title, company, job_id = match
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": f"https://www.seek.com.au/job/{job_id}"
                        })
                    if jobs:
                        break
        except Exception as e:
            print(f"Script extraction failed: {e}")

    return jobs[:MAX_JOBS]


# --- POST TO SLACK ---
def post_to_slack(all_results):
    client = WebClient(token=SLACK_TOKEN)

    total_jobs = sum(len(jobs) for _, jobs in all_results)

    if total_jobs == 0:
        client.chat_postMessage(
            channel=CHANNEL_ID,
            text="No job listings found on Seek today. Will check again in 3 days."
        )
        return

    message_blocks = ["<!channel> 🔔 *Latest Business Analyst & Senior Business Analyst Jobs on Seek:*\n"]

    for search, jobs in all_results:
        keyword = search["keyword"].title()
        location = search["location"]

        if not jobs:
            continue

        section = f"\n*{keyword} — {location}:*\n"
        job_lines = []
        for i, job in enumerate(jobs, start=1):
            line = f"{i}. *{job['title']}*\n   🏢 {job['company']}  📍 {job['location']}\n   🔗 {job['link']}"
            job_lines.append(line)

        section += "\n\n".join(job_lines)
        message_blocks.append(section)

    full_message = "\n".join(message_blocks)

    try:
        client.chat_postMessage(channel=CHANNEL_ID, text=full_message)
        print(f"Posted {total_jobs} jobs to Slack successfully.")
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")


# --- MAIN ---
if __name__ == "__main__":
    all_results = []
    for search in SEARCHES:
        print(f"Searching: {search['keyword']} in {search['location']}")
        jobs = scrape_seek_jobs(search["keyword"], search["location"])
        print(f"Found {len(jobs)} jobs")
        all_results.append((search, jobs))

    post_to_slack(all_results)
