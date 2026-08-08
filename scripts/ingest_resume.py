"""CLI wrapper — ingest resume PDF into Job OS profile."""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from job_os.services.resume_ingest import ingest, sync_world_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest resume PDF into Job OS")
    parser.add_argument("pdf", nargs="?", default=None, help="Path to resume PDF")
    parser.add_argument("--no-sync-world", action="store_true")
    args = parser.parse_args()

    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        resume_dir = ROOT / "resume"
        pdfs = list(resume_dir.glob("*.pdf")) if resume_dir.exists() else []
        if not pdfs:
            sys.exit("No PDF in resume/ folder.")
        pdf_path = pdfs[0]

    if not pdf_path.exists():
        sys.exit(f"File not found: {pdf_path}")

    ingest(pdf_path)
    if not args.no_sync_world:
        try:
            asyncio.run(sync_world_model())
        except Exception as exc:
            print(f"(world model sync skipped: {exc})")


if __name__ == "__main__":
    main()
