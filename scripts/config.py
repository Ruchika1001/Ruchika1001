import os

USERNAME = os.getenv("GH_USERNAME", "Ruchika1001")
GH_TOKEN = os.environ["GH_TOKEN"].strip()

GRAPHQL_URL = "https://api.github.com/graphql"
REST_BASE = "https://api.github.com"

# Year range for contribution history
START_YEAR = 2016
END_YEAR = 2026

# Rate-limit / retry
MAX_RETRIES = 5
BACKOFF_BASE = 1.5  # seconds

# Top-N limits
TOP_LANGUAGES = 8
TOP_REPOS = 5
