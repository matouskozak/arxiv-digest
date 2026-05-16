import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from arxiv_fetcher import fetch_arxiv_papers
from paper_filter import filter_papers_with_llm
from summarizer import summarize_papers
from issue_creator import create_issue
from github_client import GitHubClient
from utils import load_config

def create_openai_client(base_url, api_key):
    """Create and return an OpenAI client.
    
    Args:
        base_url: The base URL for the LLM API endpoint.
        api_key: The API key for authentication.
    """
    if not api_key:
        raise ValueError("API key is not set.")
    
    print(f"Creating OpenAI client with base URL: {base_url}")
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def main():
    load_dotenv()
    print("Starting Paper Summarizer...")
    config = load_config()
    
    # Extract config values
    arxiv_config = config.get("arxiv", {})
    
    github_config = config["github"]
    usernames = github_config.get("usernames", [])
    issue_label = github_config.get("issue_label", "arxiv-summary")
    max_papers_per_issue = github_config.get("max_papers_per_issue", 10)
    
    openai_base_url = config["llm_service"]["base_url"]
    api_key = config["llm_service"]["api_key"]
    filter_model = config["models"]["filter"]
    summarize_model = config["models"]["summarize"]
    
    # Create clients
    openai_client = create_openai_client(openai_base_url, api_key)
    github_client = GitHubClient()
    
    # 0. Determine start date
    last_run = github_client.get_last_issue_date(issue_label)
    if last_run:
        print(f"Last run found: {last_run}")
        last_run = last_run - timedelta(hours=1)  # Buffer of 1 hour
    else:
        last_run = datetime.now() - timedelta(days=14)
        print(f"No previous run found. Fetching papers from last 14 days (since {last_run}).")
    end_date = datetime.now()

    # 1. Fetch papers from arXiv
    print("--- Step 1: Fetching Papers ---")
    papers = fetch_arxiv_papers(
        categories=arxiv_config["categories"],
        since_date=last_run,
        max_results=arxiv_config.get("max_results", 1000),
    )
    
    if not papers:
        print("No new papers found.")
        return

    # 2. Filter (LLM)
    print("--- Step 2: Filtering Papers ---")
    keywords = config["keywords"]
    relevant_papers = filter_papers_with_llm(papers, keywords, filter_model, openai_client)
    if not relevant_papers:
        print("No relevant papers found after filtering.")
        return

    # 3. Summarize
    print("--- Step 3: Summarizing Papers ---")
    summarized_papers = summarize_papers(relevant_papers, summarize_model, openai_client)

    # 4. Create Issue
    print("--- Step 4: Creating GitHub Issue ---")
    try:
        create_issue(github_client, summarized_papers, usernames, issue_label, last_run, end_date, max_papers_per_issue=max_papers_per_issue)
    except RuntimeError as e:
        print(f"Error: {e}")
        exit(1)
    
    print("Done!")

if __name__ == "__main__":
    main()
