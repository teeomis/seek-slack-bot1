import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup

# --- CONFIG ---
SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]   # stored in GitHub Secrets
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]   # stored in GitHub Secrets
JOB_KEYWORD = "business analyst"              # change to your job title
JOB_LOCATION = "Brisbane"                     # change to your city
MAX_JOBS = 5                                   # number of jobs to post

# --- SCRAPE SEEK ---
def scrape_seek_jobs(keyword, location):
    search_term = keyword.replace(" ", "-")
    url = f"https://www.seek.com.au/{search_term}-jobs/in-{location}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        print(f"Failed to fetch Seek page. Status code: {response.status_code}")
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
def post_to_slack(jobs):
    client = WebClient(token=SLACK_TOKEN)

    if not jobs:
        message = "No job listings found on Seek today. Will check again in 3 days."
        client.chat_postMessage(channel=CHANNEL_ID, text=message)
        return

    intro = f"🔔 *Latest {JOB_KEYWORD.title()} jobs on Seek — {JOB_LOCATION}:*\n"
    job_lines = []

    for i, job in enumerate(jobs, start=1):
        line = f"{i}. *{job['title']}*\n   🏢 {job['company']}  📍 {job['location']}\n   🔗 {job['link']}"
        job_lines.append(line)

    full_message = intro + "\n\n" + "\n\n".join(job_lines)

    try:
        client.chat_postMessage(channel=CHANNEL_ID, text=full_message)
        print(f"Posted {len(jobs)} jobs to Slack successfully.")
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")


# --- MAIN ---
if __name__ == "__main__":
    print(f"Searching Seek for: {JOB_KEYWORD} in {JOB_LOCATION}")
    jobs = scrape_seek_jobs(JOB_KEYWORD, JOB_LOCATION)
    print(f"Found {len(jobs)} jobs")
    post_to_slack(jobs)
