# ArXiv Paper Summarizer

A GitHub Actions workflow that fetches recent ArXiv papers, filters them using LLMs, summarizes them, and publishes the results as GitHub Issues.

## Features
- **Smart Filtering**: Uses LLMs (e.g., GPT-5-mini) to score paper relevance (0-10) based on your keywords.
- **Concise Summaries**: Generates high-quality summaries using capable models (e.g., GPT-5).
- **Flexible LLM Support**: Works with GitHub Models (default), OpenAI, Azure OpenAI, or any OpenAI-compatible API.
- **Incremental Fetching**: Only fetches papers published since the last run to avoid duplicates.
- **Daily Schedule**: Runs automatically every day at 07:00 UTC.
- **Reading List**: Mark papers to read later with a checkbox, automatically tracked in a dedicated issue.

## Configuration

Edit `config.yaml` to customize your preferences:

```yaml
arxiv:
  categories:
    - "cs.AI"
    - "cs.LG"
  keywords:
    - "LLM"
    - "Agent"
  max_results: 20

github:
  usernames:
    - "your-username" # Users to tag in the issue
  issue_label: "arxiv-summary"
  max_papers_per_issue: 10 # Split into multiple issues when more papers are found

llm_service:
  base_url: "https://models.github.ai/inference"
  # API key is read from LLM_API_KEY env var, falling back to GITHUB_TOKEN if not set

models:
  filter: "gpt-4.1-mini"
  summarize: "gpt-4.1"
```

### Using Other LLM Providers

The tool supports any OpenAI-compatible API. Configure `llm_service` in `config.yaml`:

```yaml
# OpenAI
llm_service:
  base_url: "https://api.openai.com/v1"

# Azure OpenAI
llm_service:
  base_url: "https://<resource>.openai.azure.com/openai/deployments/<deployment>"
```

Set your API key via environment variable:
- `LLM_API_KEY` - Your provider's API key (falls back to `GITHUB_TOKEN` if not set)
- `LLM_BASE_URL` - Optionally override the base URL

## GitHub Actions

### ArXiv Summarizer

The workflow is defined in `.github/workflows/summarize.yml`. It is configured to run:
- **Daily** at 07:00 UTC.
- **Manually** via the "Run workflow" button in the Actions tab.

#### Using Custom LLM Providers in GitHub Actions

To use a different LLM provider in GitHub Actions, add these repository secrets:

1. `LLM_BASE_URL` - The API endpoint (e.g., `https://api.openai.com/v1`)
2. `LLM_API_KEY` - Your provider's API key

If these secrets are not set, the workflow defaults to GitHub Models with `GITHUB_TOKEN`.

### Reading List

Each paper summary includes a "📚 Read Later" checkbox. When you check this box:

1. A GitHub workflow detects the change (`.github/workflows/reading-list.yml`)
2. The paper title and ArXiv link are automatically added to a **📚 ArXiv Reading List** issue
3. The reading list issue is created automatically if it doesn't exist (labeled `reading-list`)

This lets you quickly bookmark interesting papers while reviewing the daily digest, with all your selections tracked in one place.

## Local Development & Testing

You can run the tool locally without GitHub Actions.

### Prerequisites
1. Install [uv](https://github.com/astral-sh/uv) (or use pip).
2. A GitHub Personal Access Token (PAT) with `repo` scope (for creating issues) and access to GitHub Models.

### Setup
```bash
# Install dependencies
uv sync
```

### Running Locally
1. Create a `.env` file in the root directory:
   ```bash
   GITHUB_TOKEN=your_fine_grained_token
   GITHUB_REPOSITORY=owner/repo
   
   # Optional: Use a different LLM provider
   # LLM_BASE_URL=https://api.openai.com/v1
   # LLM_API_KEY=your_openai_key
   ```
2. Run the summarizer:
   ```bash
   uv run src/main.py
   ```

**Token Permissions (Fine-grained):**
- **Issues**: `Read and Write` (to create summaries and check last run).
- **Models**: `Read` (to access GitHub models.)

> [!NOTE]
> When running locally, the tool will try to create a real issue in the specified repository. If you just want to test the fetching/summarizing logic without creating an issue, you can modify `src/main.py` or `src/issue_creator.py` temporarily.
