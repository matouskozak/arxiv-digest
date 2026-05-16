import os
import yaml
import tempfile
import requests
import fitz  # PyMuPDF
import time
import random
from pathlib import Path
from datetime import datetime
from openai import RateLimitError, APIStatusError


def _get_retry_delay(e, attempt, base_delay, max_delay):
    """Calculate retry delay, respecting Retry-After header if present."""
    retry_after = None
    if hasattr(e, 'response') and e.response is not None:
        retry_after = e.response.headers.get('Retry-After') or e.response.headers.get('retry-after')
    
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    
    # Exponential backoff with jitter
    return min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)


def call_with_retry(func, max_retries=5, base_delay=1.0, max_delay=60.0):
    """
    Call a function with exponential backoff retry on rate limit errors.
    
    Respects Retry-After header from GitHub Models API when available.
    
    Args:
        func: A callable (typically a lambda) that makes the API call
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries in seconds
    
    Returns:
        The result of the function call
    
    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (RateLimitError, APIStatusError) as e:
            # Only retry APIStatusError if it's a 429
            if isinstance(e, APIStatusError) and e.status_code != 429:
                raise e
            
            last_exception = e
            if attempt == max_retries:
                raise e
            
            delay = _get_retry_delay(e, attempt, base_delay, max_delay)
            print(f"Rate limited. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(delay)
    
    raise last_exception


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load, validate and return the config file with defaults applied.
    
    Args:
        config_path: Path to the config file (default: config.yaml)
    
    Returns:
        Parsed config dictionary with defaults applied
    
    Raises:
        ValueError: If required config fields are missing
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Validate keywords (used for LLM filtering)
    if "keywords" not in config or not config["keywords"]:
        raise ValueError("Config missing 'keywords'")
    
    # Validate arxiv section
    arxiv = config.get("arxiv", {})
    if "categories" not in arxiv or not arxiv["categories"]:
        raise ValueError("Config missing 'arxiv.categories'")
    
    # Validate github section
    if "github" not in config:
        config["github"] = {}
    
    # Apply llm_service defaults
    if "llm_service" not in config:
        config["llm_service"] = {}
    config["llm_service"].setdefault("base_url", "https://models.github.ai/inference")
    
    # Allow environment variables to override config values
    if os.environ.get("LLM_BASE_URL"):
        config["llm_service"]["base_url"] = os.environ["LLM_BASE_URL"]
    
    # API key: env var takes precedence, fallback to GITHUB_TOKEN for default provider
    config["llm_service"]["api_key"] = os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN")
    
    # Apply models defaults
    if "models" not in config:
        config["models"] = {}
    config["models"].setdefault("filter", "gpt-4.1-mini")
    config["models"].setdefault("summarize", "gpt-4.1")
    
    return config


def extract_text_from_pdf(pdf_url, max_chars=50000):
    """Download PDF and extract text content."""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
            tmp_file.write(response.content)
            tmp_file.flush()
            
            doc = fitz.open(tmp_file.name)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            
            # Truncate to avoid token limits
            if len(text) > max_chars:
                text = text[:max_chars] + "\n... [truncated]"
            
            return text
    except Exception as e:
        print(f"    Warning: Could not extract PDF text: {e}")
        return None


def is_running_in_ci() -> bool:
    """Check if we're running in a GitHub Actions workflow."""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def get_tmp_dir(subdir: str) -> Path:
    """Get the tmp directory path for a given subdirectory."""
    tmp_dir = Path(__file__).parent.parent / "tmp" / subdir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def get_timestamp() -> str:
    """Get current timestamp in a filename-safe format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Create a safe filename from a string."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name[:max_length])


def save_to_tmp(subdir: str, filename: str, content: str) -> Path:
    """
    Save content to a file in the tmp directory.
    
    Args:
        subdir: Subdirectory within tmp (e.g., 'summaries', 'issues')
        filename: Name of the file to create
        content: Content to write to the file
    
    Returns:
        Path to the saved file
    """
    tmp_dir = get_tmp_dir(subdir)
    filepath = tmp_dir / filename
    
    with open(filepath, "w") as f:
        f.write(content)
    
    return filepath


def save_summary_to_tmp(paper: dict, summary_text: str) -> Path | None:
    """Save individual paper summary to tmp folder for inspection (local only)."""
    if is_running_in_ci():
        return None
    
    safe_title = sanitize_filename(paper['title'])
    timestamp = get_timestamp()
    filename = f"{timestamp}_{safe_title}.md"
    
    content = f"# {paper['title']}\n\n"
    content += f"**Authors:** {', '.join(paper['authors'])}\n\n"
    content += f"**Abstract:** {paper['abstract']}\n\n"
    content += "---\n\n"
    content += "## LLM Summary\n\n"
    content += summary_text
    
    file_path = save_to_tmp("summaries", filename, content)
    print(f"Summary saved to: {file_path}")
    return file_path


def save_issue_to_tmp(title: str, body: str, suffix: str = "") -> Path | None:
    """Save the issue content to tmp folder before posting to GitHub (local only)."""
    if is_running_in_ci():
        return None
    
    timestamp = get_timestamp()
    filename = f"{timestamp}_issue{suffix}.md"
    
    content = f"# {title}\n\n{body}"
    
    filepath = save_to_tmp("issues", filename, content)
    print(f"Issue saved to: {filepath}")
    return filepath
