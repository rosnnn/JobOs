from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProfessionalIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "professional_identities"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role_focus: Mapped[str] = mapped_column(String(128))
    ats_keywords: Mapped[list] = mapped_column(JSONB, default=list)
    project_emphasis: Mapped[list] = mapped_column(JSONB, default=list)
    tone: Mapped[str] = mapped_column(String(64), default="professional")
    base_resume_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    performance_stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)

    resumes = relationship("Resume", back_populates="identity")
    applications = relationship("Application", back_populates="identity")


class Resume(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resumes"

    identity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professional_identities.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tailored_for_job_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    identity = relationship("ProfessionalIdentity", back_populates="resumes")
    applications = relationship("Application", back_populates="resume")


class CoverLetter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cover_letters"

    job_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), index=True)
    identity_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professional_identities.id"), nullable=True
    )
    content_text: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    applications = relationship("Application", back_populates="cover_letter")
