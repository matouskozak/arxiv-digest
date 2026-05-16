from datetime import datetime
from math import ceil
from models import Paper, PaperSummary
from utils import save_issue_to_tmp


def format_summary(summary):
    """Format a summary into markdown."""
    if isinstance(summary, PaperSummary):
        return summary.to_markdown()
    return str(summary)


def _format_paper(paper: Paper) -> str:
    body = f"## {paper.title}\n"
    body += f"**Authors:** {', '.join(paper.authors)}\n\n"
    body += f"### Summary\n{format_summary(paper.summary)}\n\n"
    body += f"[View on ArXiv]({paper.link})\n\n"
    body += f"- [ ] 📚 Read Later\n\n"
    body += "---\n\n"
    return body


def create_issue(github_client, papers: list[Paper], usernames=None, issue_label="arxiv-summary", start_date=None, end_date=None, max_papers_per_issue: int = 10):
    if usernames is None:
        usernames = []

    if not papers:
        return

    if max_papers_per_issue <= 0:
        raise ValueError("max_papers_per_issue must be a positive integer")

    # Format Issue Title with time range
    date_str = datetime.now().strftime("%Y-%m-%d")
    if start_date and end_date:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        base_title = f"ArXiv Summary - {date_str} (papers from {start_str} to {end_str})"
    else:
        base_title = f"ArXiv Summary - {date_str}"

    total_papers = len(papers)
    total_parts = ceil(total_papers / max_papers_per_issue)

    for part_idx in range(total_parts):
        start = part_idx * max_papers_per_issue
        end = min(start + max_papers_per_issue, total_papers)
        chunk = papers[start:end]

        if total_parts > 1:
            title = f"{base_title} (Part {part_idx + 1}/{total_parts})"
            range_note = f"Papers {start + 1}-{end} of {total_papers} (Part {part_idx + 1}/{total_parts}).\n\n"
            tmp_suffix = f"_part{part_idx + 1}of{total_parts}"
        else:
            title = base_title
            range_note = ""
            tmp_suffix = ""

        body = f"# ArXiv Paper Summaries ({date_str})\n\n"
        body += f"Found {total_papers} relevant papers.\n\n"
        body += range_note

        for paper in chunk:
            body += _format_paper(paper)

        # Save issue to tmp folder before posting
        save_issue_to_tmp(title, body, suffix=tmp_suffix)

        # Create Issue via API
        github_client.create_issue(
            title=title,
            body=body,
            labels=[issue_label],
            assignees=usernames if usernames else None
        )


if __name__ == "__main__":
    from github_client import GitHubClient
    from utils import load_config
    
    config = load_config()
    
    usernames = config.get("github", {}).get("usernames", [])
    issue_label = config.get("github", {}).get("issue_label", "arxiv-summary")
    
    # Test with dummy data (will fail locally without correct env vars)
    try:
        client = GitHubClient()
        dummy_papers = [Paper(
            title="Test Paper",
            authors=["Me", "You"],
            link="http://arxiv.org/abs/1234.5678",
            abstract="Test abstract",
            summary=PaperSummary(
                problem="Test problem",
                proposed_method="Test method",
                key_results="Test results"
            )
        )]
        create_issue(client, dummy_papers, usernames, issue_label)
    except ValueError as e:
        print(f"Test skipped: {e}")
