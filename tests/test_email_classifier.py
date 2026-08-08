"""Tests for email classification."""

from job_os.services.email_classifier import EmailClassifier


def test_rejection_not_app_received_thank_you():
    c = EmailClassifier()
    result = c.classify(
        "Update on your application with Conga",
        "Hi Roshan, Thank you for your interest in the Information Systems Engineer role. "
        "While we were impressed with your background, we've chosen to move forward with "
        "another candidate whose experience more closely fits this role.",
        "careers@conga.com",
    )
    assert result["outcome"] == "rejected"


def test_rejection_subject_your_application_for_role():
    c = EmailClassifier()
    result = c.classify(
        "Your Application for Trainee - Associate Software Maintenance Engineer",
        "Thank you for applying. We reviewed your profile.",
        "careers@company.com",
    )
    assert result["outcome"] == "rejected"


def test_rejection_thank_you_plus_unfortunately():
    c = EmailClassifier()
    result = c.classify(
        "Regarding your application",
        "Thank you for applying to our team. Unfortunately we will not be moving forward.",
        "talent@acme.com",
    )
    assert result["outcome"] == "rejected"


def test_atlassian_completion_not_rejection():
    c = EmailClassifier()
    result = c.classify(
        "Atlassian: Thanks for Completing Your Application",
        "Thank you for completing your application. Our recruiting team will review it.",
        "noreply@greenhouse.io",
    )
    assert result["outcome"] in ("application_received", "employer_update")
    assert result["outcome"] != "rejected"


def test_naukri_profile_update_not_rejection():
    c = EmailClassifier()
    result = c.classify(
        "Update: Roshan, your job profile status needs an important application update",
        "Update your Naukri profile to get more recruiter views.",
        "noreply@naukri.com",
    )
    assert result["outcome"] != "rejected"


def test_rejection_wipro_style():
    c = EmailClassifier()
    result = c.classify(
        "Update on your application",
        "<p>Unfortunately, after reviewing your profile, we regret that we will not be "
        "taking your application forward for this role.</p>",
        "careers@wipro.com",
    )
    assert result["outcome"] == "rejected"


def test_application_received_only_when_pure_ack():
    c = EmailClassifier()
    result = c.classify(
        "Application received",
        "Thank you for applying. We have received your application and our team will review it.",
        "noreply@greenhouse.io",
    )
    assert result["outcome"] == "application_received"


def test_classify_security():
    c = EmailClassifier()
    result = c.classify(
        "Security alert",
        "A new sign-in on Windows was detected on your Google Account.",
        "no-reply@accounts.google.com",
    )
    assert result["outcome"] == "security"


def test_classify_job_recommendation_linkedin():
    c = EmailClassifier()
    result = c.classify(
        "10 new jobs for you",
        "See jobs matching your profile",
        "jobs-noreply@linkedin.com",
    )
    assert result["outcome"] == "job_recommendation"


def test_no_other_category():
    c = EmailClassifier()
    result = c.classify("Random subject", "Some random body text here.", "foo@bar.com")
    assert result["outcome"] != "other"
    assert result["outcome"] in ("general_notification", "job_related", "promotional")
