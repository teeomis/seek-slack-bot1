import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        print(f"Failed to fetch Seek page for {keyword} in {location}. Status: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    job_cards = soup.find_all("article", limit=MAX_JOBS)

    jobs = []
    for card in job_cards:
        try:
            title_tag = card.find("a", {"data-automation": "jobTitle"})
            company_tag = card.find("a", {"data-automation": "jobCompany"})
            location_tag = card.find("span", {"data-automation": "jobCardLocation"})

            title = title_tag.text.strip() if title_tag else "No title"
            company = company_tag.text.strip() if company_tag else "No company"
            location_text = location_tag.text.strip() if location_tag else ""
            link = "https://www.seek.com.au" + title_tag["href"] if title_tag else ""

            jobs.append({
                "title": title,
                "company": company,
                "location": location_text,
                "link": link
            })
        except Exception as e:
            print(f"Error parsing job card: {e}")
            continue

    return jobs


# --- POST TO SLACK ---
def post_to_slack(all_results):
    client = WebClient(token=SLACK_TOKEN)

    if not all_results:
        client.chat_postMessage(
            channel=CHANNEL_ID,
            text="No job listings found on Seek today. Will check again in 3 days."
        )
        return

    message_blocks = ["🔔 *Latest Business Analyst & Senior Business Analyst Jobs on Seek:*\n"]

    for search, jobs in all_results:
        keyword = search["keyword"].title()
        location = search["location"]

        if not jobs:
            message_blocks.append(f"\n*{keyword} — {location}*\nNo listings found.\n")
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
        print("Posted all jobs to Slack successfully.")
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
