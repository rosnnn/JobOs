"""Common ATS application fields (Greenhouse, Lever, Workday, Ashby, iCIMS).

Sources: public ATS documentation and typical EEO / compliance question sets.
We match by label/name patterns — not site-specific selectors.
"""

from __future__ import annotations

# Each entry: (patterns in label/name/id), answer_key in merged application profile
FIELD_RULES: list[tuple[tuple[str, ...], str]] = [
    # Compensation
    (("desired salary", "salary expectation", "compensation", "pay expectation", "expected salary", "ctc", "package"), "compensation.desired_salary_usd_annual"),
    (("lpa", "lakhs", "ctc in"), "compensation.expected_ctc_lpa"),
    (("hourly", "per hour"), "compensation.hourly_rate_usd"),
    # Demographics / EEO (US-style; answer truthfully per user settings)
    (("gender", "sex"), "demographics.gender"),
    (("race", "ethnicity", "hispanic"), "demographics.race_ethnicity"),
    (("disability", "handicap"), "demographics.disability_status"),
    (("veteran", "protected veteran", "military"), "demographics.veteran_status"),
    (("lgbtq", "sexual orientation"), "demographics.lgbtq_identify"),
    # Company relationship
    (("previously employed", "previously worked", "worked at", "former employee", "ever worked for"), "company_screening.previously_employed_at_company"),
    (("relative", "family member", "affiliated", "know anyone", "related to anyone"), "company_screening.relative_employed_at_company"),
    (("conflict of interest",), "company_screening.conflict_of_interest"),
    (("non-compete", "non compete"), "company_screening.non_compete"),
    # Work authorization
    (("visa sponsorship", "require sponsorship", "immigration sponsorship", "need sponsorship"), "work_authorization_answers.requires_visa_sponsorship"),
    (("authorized to work", "legally authorized", "work authorization", "work permit", "right to work"), "work_authorization_answers.legally_authorized"),
    (("authorized to work in the us", "eligible to work in us"), "work_authorization_answers.authorized_to_work_us"),
    # Availability
    (("start date", "available to start", "earliest start", "joining date", "notice period"), "availability.start_date"),
    (("days until", "how soon", "when can you start"), "availability.notice_period_days"),
    (("relocate", "relocation", "willing to move"), "availability.willing_to_relocate"),
    (("travel", "willing to travel"), "availability.willing_to_travel"),
    (("how did you hear", "how did you learn", "referral source", "source of application"), "how_did_you_hear"),
    # Consent
    (("background check",), "company_screening.background_check_consent"),
    (("drug test", "drug screen"), "company_screening.drug_test_consent"),
]

ATS_PAGE_HINTS = {
    "greenhouse": ["greenhouse", "boards.greenhouse"],
    "lever": ["lever.co", "jobs.lever"],
    "workday": ["myworkdayjobs", "workday"],
    "ashby": ["ashbyhq"],
    "icims": ["icims"],
}
