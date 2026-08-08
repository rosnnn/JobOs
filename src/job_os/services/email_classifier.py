"""Classify inbox emails — rejection-first, full body read, no vague 'other'."""

from __future__ import annotations

import html
import re
from typing import Any

# Strong rejection signals (checked BEFORE application_received / thank-you phrases)
REJECTION_PATTERNS = [
    r"unfortunately",
    r"we regret",
    r"regret to inform",
    r"not moving forward",
    r"not be moving forward",
    r"won'?t be moving forward",
    r"will not be moving forward",
    r"decided not to move forward",
    r"decided to pursue other",
    r"will not be proceeding",
    r"not be proceeding",
    r"not be progressing",
    r"not advancing",
    r"not selected",
    r"weren'?t selected",
    r"were not selected",
    r"not chosen",
    r"other candidates?",
    r"another candidate",
    r"move forward with another",
    r"moving forward with another",
    r"chosen to move forward with another",
    r"position has been filled",
    r"role has been filled",
    r"job has been filled",
    r"no longer considering",
    r"not successful",
    r"application was not",
    r"application has been declined",
    r"application.{0,40}declined",
    r"we will not be taking your application",
    r"not taking your application forward",
    r"unable to offer you",
    r"cannot offer you",
    r"after careful (review|consideration).{0,80}(not|unable|regret|other)",
    r"while we were impressed.{0,120}(another|other|not)",
    r"although your .{0,40} impressive.{0,80}(not|other|another)",
    r"at this time we are not",
    r"we have decided not to",
    r"we'?ve decided not to",
    r"not a fit for",
    r"not the right fit",
    r"will not be considered",
    r"closed the position",
    r"filled the position",
    r"update on your application",  # common rejection subject from ATS
    r"update: your job application",
    r"status of your application",
    r"regarding your application for",
    r"your application (to|for).{0,60}(update|status)",
    r"application update",
    r"not proceed with your",
    r"did not advance",
    r"will not advance",
]

REJECTION_SUBJECT_ONLY = [
    r"^update[:\s]+your (job )?application",
    r"^update on your application",
    r"application (update|status|decision)",
    r"regarding your application",
    r"your application (at|with|to|for)",
    r"not selected",
    r"application rejected",
    r"unfortunately",
]

INTERVIEW_PATTERNS = [
    r"interview (invite|invitation|scheduled|confirmation)",
    r"schedule (a |an )?(call|interview|meeting|time)",
    r"invite you (for|to) (an |a )?interview",
    r"phone screen",
    r"technical (round|interview|assessment)",
    r"assessment (link|invite|url)",
    r"coding (challenge|test|assessment)",
    r"hacker ?rank",
    r"codility",
    r"meet the team",
    r"next (round|step) in (our |the )?(hiring |selection )?process",
    r"availability for (a |an )?interview",
    r"would like to interview",
    r"interviewing you",
]

OFFER_PATTERNS = [
    r"offer letter",
    r"pleased to offer",
    r"extend (an |our )?offer",
    r"job offer",
    r"compensation package",
    r"congratulations.{0,40}offer",
]

ACCEPTED_PATTERNS = [
    r"welcome aboard",
    r"welcome to the team",
    r"onboarding (process|schedule|call|details)",
    r"looking forward to having you join",
    r"you will be joining",
]

# Strict: ONLY if no rejection signals present
APPLICATION_RECEIVED_PATTERNS = [
    r"we (have )?received your application",
    r"application (has been )?received",
    r"successfully (submitted|received)",
    r"application confirmation",
    r"confirm(s|ing)? (we )?received",
    r"thank you for (submitting|applying)",
    r"thanks for (submitting|applying)",
    r"thanks? for completing your application",
    r"your application (has been |was )?submitted",
]

JOB_BOARD_FROM = [
    r"linkedin", r"indeed", r"naukri", r"glassdoor", r"wellfound", r"foundit",
    r"instahyre", r"cutshort", r"hirist", r"remoteok", r"jobicy", r"remotive",
    r"arbeitnow", r"ziprecruiter", r"monster", r"careerbuilder", r"simplyhired",
    r"shine\.com", r"timesjobs", r"internshala", r"unstop", r"foundit",
]

JOB_RECOMMENDATION_PATTERNS = [
    r"jobs? (for you|recommended|matching|alert)",
    r"new jobs? (posted|for you|matching)",
    r"recommended (jobs?|roles?|positions?)",
    r"job alert",
    r"apply to these jobs",
    r"top jobs? for you",
    r"your (daily|weekly) job",
    r"similar jobs",
    r"careers? you may like",
    r"\d+ new jobs",
]

NEWSLETTER_PATTERNS = [
    r"newsletter",
    r"digest",
    r"weekly update",
    r"monthly update",
    r"unsubscribe",
    r"open rate",
    r"view in browser",
]

EDUCATION_PROMO_PATTERNS = [
    r"mba",
    r"course",
    r"program",
    r"admissions?",
    r"institute",
    r"college",
    r"assured roi",
    r"enroll now",
]

PROMOTIONAL_PATTERNS = [
    r"unsubscribe",
    r"%\s*off",
    r"limited time offer",
    r"shop now",
    r"buy now",
    r"discount code",
    r"flash sale",
    r"exclusive deal",
    r"claim your (free|discount)",
    r"special offer",
]

SECURITY_PATTERNS = [
    r"security alert",
    r"suspicious sign-?in",
    r"new sign-?in",
    r"2-?step verification",
    r"google account",
    r"unusual activity",
    r"password (was|has been) changed",
]

WALKIN_PATTERNS = [
    r"walk-?in",
    r"walk in (drive|interview)",
    r"on-?site (today|tomorrow)",
    r"immediate joining",
]


def normalize_email_text(subject: str, body: str) -> tuple[str, str]:
    """Strip HTML/CSS and extract readable text for accurate matching."""

    def clean(s: str) -> str:
        if not s:
            return ""
        s = html.unescape(s)
        s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
        s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
        # Pull visible text chunks from HTML tags (ATS templates hide text in <p>/<td>)
        chunks = re.findall(
            r">([^<]{12,}?)(?:<|$)",
            s,
            flags=re.S,
        )
        visible = " ".join(chunks) if chunks else s
        visible = re.sub(r"<[^>]+>", " ", visible)
        visible = re.sub(r"#outlook[^{]*\{[^}]*\}", " ", visible, flags=re.I)
        visible = re.sub(r"@[a-z]+\s*\{[^}]*\}", " ", visible, flags=re.I)
        visible = re.sub(r"\{[^}]*\}", " ", visible)
        visible = re.sub(r"[^\S\n]+", " ", visible)
        return visible.strip().lower()

    return clean(subject), clean(body)[:12000]


class EmailClassifier:
    def classify(self, subject: str, body: str, from_address: str = "") -> dict[str, Any]:
        subject_l, body_l = normalize_email_text(subject, body)
        from_l = (from_address or "").lower()
        text = f"{subject_l} {body_l}"

        rejection_reason: str | None = None
        is_walk_in = any(re.search(p, text, re.I) for p in WALKIN_PATTERNS)

        outcome = self._classify_with_priority(subject_l, body_l, text, from_l)

        if outcome == "interview_request" or is_walk_in:
            pass
        elif is_walk_in:
            outcome = "interview_request"

        if outcome == "rejected":
            rejection_reason = self._extract_rejection_reason(body_l)

        company = self._guess_company(subject, body, from_address)
        return {
            "outcome": outcome,
            "rejection_reason": rejection_reason,
            "is_walk_in": is_walk_in,
            "is_interview": outcome == "interview_request",
            "company_name": company,
        }

    def _classify_with_priority(self, subject_l: str, body_l: str, text: str, from_l: str) -> str:
        # 1. Security (Google etc.)
        if any(re.search(p, from_l, re.I) for p in (r"google\.com", r"accounts\.google", r"security@")):
            if self._any_match(SECURITY_PATTERNS, text):
                return "security"

        if self._any_match(SECURITY_PATTERNS, text) and "application" not in text:
            return "security"

        # 2. REJECTION FIRST — before thank-you / application received
        if self._is_rejection(subject_l, body_l, text, from_l):
            return "rejected"

        # 3. Interview / offer / hired
        if self._any_match(INTERVIEW_PATTERNS, text):
            return "interview_request"
        if self._any_match(OFFER_PATTERNS, text):
            return "offer"
        if self._any_match(ACCEPTED_PATTERNS, text):
            return "accepted"

        # 4. Job boards — recommendations (not employer reply)
        if any(re.search(p, from_l, re.I) for p in JOB_BOARD_FROM):
            if self._any_match(NEWSLETTER_PATTERNS, text):
                return "newsletter"
            if self._any_match(EDUCATION_PROMO_PATTERNS, text):
                return "promotional"
            if self._any_match(JOB_RECOMMENDATION_PATTERNS, text):
                return "job_recommendation"
            if self._looks_job_related(text, from_l):
                return "job_recommendation"
            return "general_notification"

        if self._any_match(JOB_RECOMMENDATION_PATTERNS, text):
            return "job_recommendation"

        # 5. Promo / sponsorship
        if self._any_match(PROMOTIONAL_PATTERNS, text):
            return "promotional"
        if re.search(r"sponsor(ship)? (opportunit|program)|paid partnership|brand collaboration", text, re.I):
            return "sponsorship_ad"

        # 6. Application received — ONLY if clearly acknowledgment, not rejection
        if self._any_match(APPLICATION_RECEIVED_PATTERNS, text):
            if not self._is_rejection(subject_l, body_l, text, from_l):
                return "application_received"

        # 7. HR outreach (recruiter reaching out, not ATS auto-reply)
        if self._any_match(
            [r"would you be interested", r"came across your profile", r"reach(ing)? out regarding", r"hiring for"],
            text,
        ):
            return "hr_outreach"
        if any(re.search(p, from_l, re.I) for p in (r"recruit", r"talent@", r"hiring@")) and "application" not in text:
            return "hr_outreach"

        # 8. Employer ATS domains — only pure ack, never guess "received" from "thank you" alone
        if any(d in from_l for d in ("greenhouse", "lever", "workday", "ashby", "icims", "smartrecruiters")):
            if self._any_match(APPLICATION_RECEIVED_PATTERNS, text):
                return "application_received"
            if "application" in subject_l or "application" in body_l[:2000]:
                return "employer_update"
            return "employer_update"

        # 9. Newsletter / general commerce / OTP
        if re.search(r"newsletter|weekly digest|monthly roundup", text, re.I):
            return "newsletter"
        if re.search(r"invoice|receipt|order confirm|shipped|delivery", text, re.I):
            return "general_notification"
        if re.search(r"\botp\b|verification code|one.time password", text, re.I):
            return "general_notification"

        # 10. Job-related catch-all (no "other")
        if self._looks_job_related(text, from_l):
            return "job_related"

        # 11. Final bucket — never "other"
        if re.search(r"unsubscribe|marketing|promo", text, re.I):
            return "promotional"
        return "general_notification"

    def _is_rejection(self, subject_l: str, body_l: str, text: str, from_l: str = "") -> bool:
        # Acknowledgments — never reject
        if re.search(
            r"thanks? for (completing|submitting) your application|application (received|submitted|confirmed)",
            subject_l,
            re.I,
        ):
            return False
        if re.search(
            r"we (have )?received your application|successfully (submitted|received)",
            text,
            re.I,
        ) and not self._any_match(
            [r"unfortunately", r"regret", r"not moving forward", r"another candidate"],
            text,
        ):
            return False

        # Job boards use "application update" for profile alerts — not employer rejections
        if any(re.search(p, from_l, re.I) for p in JOB_BOARD_FROM):
            if re.search(r"profile|job alert|recommended|matching|jobs? for you", text, re.I):
                return False

        # ATS rejection subjects (checked before "thank you for applying" in body)
        if re.search(r"update[:\s]+(on )?your (job )?application", subject_l, re.I):
            return True
        if re.search(r"application (update|status|decision|not selected)", subject_l, re.I):
            if re.search(r"profile status|job profile|important application update", subject_l, re.I):
                return False
            return True
        if re.search(r"^your application (for|to|at|with)\b", subject_l, re.I):
            return True
        if re.search(r"regarding your application", subject_l, re.I):
            return True
        if re.search(r"^update:\s*your job application", subject_l, re.I):
            return True
        if any(re.search(p, subject_l, re.I) for p in REJECTION_SUBJECT_ONLY):
            return True

        if self._any_match(REJECTION_PATTERNS, text):
            return True

        # Polite rejections: "thank you for applying" + negative outcome in same mail
        if re.search(r"thank you for (your interest in|applying)", text, re.I):
            soft_reject = [
                r"unfortunately",
                r"we regret",
                r"not (be )?moving forward",
                r"not (be )?proceeding",
                r"another candidate",
                r"other candidates?",
                r"not selected",
                r"will not be taking",
                r"decided not to",
                r"not a fit",
                r"not the right fit",
                r"unable to offer",
                r"after careful (review|consideration)",
                r"while we were impressed",
                r"although your",
                r"we have decided",
                r"not advance",
                r"position has been filled",
            ]
            if self._any_match(soft_reject, text):
                return True

        return False

    @staticmethod
    def _any_match(patterns: list[str], text: str) -> bool:
        return any(re.search(p, text, re.I) for p in patterns)

    def _extract_rejection_reason(self, body: str) -> str | None:
        # Strip to readable sentence
        plain = re.sub(r"<[^>]+>", " ", body)
        plain = re.sub(r"\s+", " ", plain).strip()
        for fragment in re.split(r"[.!?]\s+", plain):
            lower = fragment.lower()
            if any(
                k in lower
                for k in (
                    "unfortunately",
                    "regret",
                    "not moving forward",
                    "another candidate",
                    "not selected",
                    "not proceeding",
                    "not be taking",
                    "move forward with another",
                    "chosen to move forward",
                )
            ):
                return fragment[:500]
        return plain[:500] if plain else None

    def _looks_job_related(self, text: str, from_addr: str) -> bool:
        if any(re.search(h, text, re.I) for h in (r"\bjob\b", r"\bcareer", r"\bapply\b", r"\bposition\b", r"\bhiring\b")):
            return True
        return any(d in from_addr for d in ("greenhouse", "lever", "workday", "ashby", "careers"))

    def _guess_company(self, subject: str, body: str, from_address: str) -> str | None:
        m = re.search(r"<([^>]+)>", from_address)
        if m:
            domain = m.group(1).split("@")[-1]
            name = domain.split(".")[0]
            if name not in ("gmail", "google", "linkedin", "indeed", "mail", "email", "noreply"):
                return name.replace("-", " ").title()[:128]

        for pat in [
            r"application (to|for|with) ([A-Z][A-Za-z0-9 &.'-]+)",
            r"role at ([A-Z][A-Za-z0-9 &.'-]+)",
            r"at ([A-Z][A-Za-z0-9 &.'-]+)\s",
        ]:
            m = re.search(pat, subject)
            if m:
                return m.group(1).strip()[:128]

        m = re.search(r"^([^:|\-\[]+)", subject)
        if m:
            name = m.group(1).strip()
            if len(name) > 2 and name.lower() not in ("re", "fw", "fwd", "security alert", "update"):
                return name[:128]
        return None
