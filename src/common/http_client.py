"""Resilient HTTP client session factory with retries and backoff."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

DEFAULT_USER_AGENT = "RiskEngine/1.0 (NLP Research; Hackathon 2026; PairProgrammer)"


def get_resilient_session(
    retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    user_agent: str = DEFAULT_USER_AGENT,
) -> requests.Session:
    """Create a requests.Session configured with automatic retry, backoff, and headers."""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
