"""Registry of job board sources — APIs, ATS boards, and aggregators."""

from __future__ import annotations

# Adzuna supported country codes (Indeed/Naukri/Glassdoor-style aggregates per region)
ADZUNA_COUNTRIES: tuple[str, ...] = (
    "in",  # India — Indeed, Naukri, Shine, etc.
    "us",  # US — Indeed, Glassdoor, etc.
    "gb",  # UK
    "au",  # Australia
    "ca",  # Canada
    "de",  # Germany
    "fr",  # France
    "sg",  # Singapore
    "nz",  # New Zealand
    "at",  # Austria
    "be",  # Belgium
    "br",  # Brazil
    "ch",  # Switzerland
    "es",  # Spain
    "it",  # Italy
    "mx",  # Mexico
    "nl",  # Netherlands
    "pl",  # Poland
    "za",  # South Africa
)

# Public Greenhouse board tokens (company career pages)
GREENHOUSE_BOARDS: tuple[str, ...] = (
    "stripe",
    "airbnb",
    "discord",
    "figma",
    "notion",
    "openai",
    "anthropic",
    "databricks",
    "cloudflare",
    "mongodb",
    "coinbase",
    "datadog",
    "hubspot",
    "brex",
    "ramp",
    "plaid",
    "scaleai",
    "anduril",
    "palantir",
    "snowflake",
    "vercel",
    "supabase",
    "linear",
    "retool",
    "rippling",
    "gusto",
    "affirm",
    "block",
    "square",
    "robinhood",
    "coursera",
    "duolingo",
    "grammarly",
    "asana",
    "dropbox",
    "twilio",
    "zendesk",
    "okta",
    "crowdstrike",
    "zscaler",
    "freshworks",
    "zomato",
    "swiggy",
    "razorpay",
    "phonepe",
    "freshworks",
)

# Public Lever company slugs
LEVER_COMPANIES: tuple[str, ...] = (
    "netflix",
    "spotify",
    "atlassian",
    "canva",
    "github",
    "shopify",
    "reddit",
    "lyft",
    "postman",
    "zerodha",
)

SOURCE_LABELS: dict[str, str] = {
    "remoteok": "RemoteOK",
    "remotive": "Remotive",
    "jobicy": "Jobicy",
    "arbeitnow": "Arbeitnow",
    "himalayas": "Himalayas (remote)",
    "weworkremotely": "We Work Remotely",
    "jobspresso": "Jobspresso",
    "startup_jobs": "Startup.jobs",
    "findwork": "Findwork.dev",
    "jsearch": "Google for Jobs (LinkedIn · Indeed · Glassdoor · Naukri · …)",
    "linkedin": "LinkedIn (logged-in browser sync)",
    "greenhouse": "Greenhouse ATS (company boards)",
    "lever": "Lever ATS (company boards)",
    "wellfound": "Wellfound (AngelList)",
    "yc_jobs": "Y Combinator jobs",
}

for cc in ADZUNA_COUNTRIES:
    labels = {
        "in": "Adzuna → Indeed · Naukri · Shine (India)",
        "us": "Adzuna → Indeed · Glassdoor · ZipRecruiter (US)",
        "gb": "Adzuna → Indeed · Reed (UK)",
        "au": "Adzuna → Indeed · Seek (Australia)",
        "ca": "Adzuna → Indeed · Workopolis (Canada)",
        "de": "Adzuna → Indeed · StepStone (Germany)",
        "sg": "Adzuna → Indeed · JobStreet (Singapore)",
    }
    SOURCE_LABELS[f"adzuna_{cc}"] = labels.get(cc, f"Adzuna job aggregate ({cc.upper()})")

DEFAULT_ENABLED_SOURCES: tuple[str, ...] = (
    "jsearch",
    "adzuna_in",
    "adzuna_us",
    "adzuna_gb",
    "adzuna_au",
    "adzuna_ca",
    "adzuna_de",
    "adzuna_sg",
    "remoteok",
    "remotive",
    "jobicy",
    "arbeitnow",
    "weworkremotely",
    "jobspresso",
    "startup_jobs",
    "findwork",
    "greenhouse",
    "lever",
    "himalayas",
    "linkedin",
    "wellfound",
)

# Aggregators first; Himalayas last (high volume, remote-only)
SOURCE_FETCH_PRIORITY: tuple[str, ...] = (
    "jsearch",
    *(f"adzuna_{c}" for c in ADZUNA_COUNTRIES),
    "findwork",
    "remoteok",
    "remotive",
    "jobicy",
    "arbeitnow",
    "weworkremotely",
    "jobspresso",
    "startup_jobs",
    "greenhouse",
    "lever",
    "linkedin",
    "wellfound",
    "yc_jobs",
    "himalayas",
)


def priority_index(source: str, home_adzuna: str) -> int:
    """Home-country Adzuna first, then global priority list."""
    order = [home_adzuna] + [s for s in SOURCE_FETCH_PRIORITY if s != home_adzuna]
    try:
        return order.index(source)
    except ValueError:
        if source.startswith("adzuna_"):
            return len(order) + 1
        return 999
