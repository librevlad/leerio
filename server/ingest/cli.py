"""CLI entry point for content ingestion pipeline."""

import argparse
import asyncio
import json
import logging
import sys

logger = logging.getLogger("leerio.ingest")


def cmd_status(args):
    """Show ingestion job status."""
    from .. import db

    db.init_db()
    jobs = db.list_ingestion_jobs(status=args.status, limit=args.limit or 20)
    if not jobs:
        print("No ingestion jobs found.")
        return
    print(f"{'ID':>5} {'Source':<12} {'Status':<12} {'Created':<20} {'Updated':<20}")
    print("-" * 75)
    for j in jobs:
        print(
            f"{j['id']:>5} {j['source']:<12} {j['status']:<12} {j['created_at'] or '':<20} {j['updated_at'] or '':<20}"
        )


def cmd_recover(args):
    """Recover stalled jobs."""
    from .. import db

    db.init_db()
    count = db.recover_stalled_jobs()
    print(f"Recovered {count} stalled job(s).")


def cmd_retry(args):
    """Retry a failed job."""
    from .. import db

    db.init_db()
    job = db.get_ingestion_job(args.job_id)
    if not job:
        print(f"Job {args.job_id} not found.")
        sys.exit(1)
    if job["status"] not in ("failed", "partial"):
        print(f"Job {args.job_id} is {job['status']}, not retryable.")
        sys.exit(1)
    db.update_ingestion_job(args.job_id, status="pending")
    print(f"Job {args.job_id} reset to pending.")


def cmd_normalize(args):
    """Normalize existing books."""
    from .. import db
    from .jobs import run_job

    db.init_db()

    input_data = {"fast": args.fast}
    if args.book_id:
        input_data["book_id"] = args.book_id
    elif not args.all:
        print("Specify --all or --book-id N")
        sys.exit(1)

    job_id = db.create_ingestion_job("normalize", input_data)
    print(f"Created normalization job #{job_id}")

    if not args.queue_only:
        asyncio.run(run_job(job_id))
        job = db.get_ingestion_job(job_id)
        print(f"Job #{job_id} finished: {job['status']}")
        if job["result"]:
            print(json.dumps(json.loads(job["result"]), indent=2, ensure_ascii=False))


def cmd_url(args):
    """Ingest from URL."""
    from .. import db
    from .jobs import run_job

    db.init_db()

    input_data = {
        "url": args.url,
        "title": args.title or "Unknown",
        "author": args.author or "Unknown",
        "reader": args.reader or "",
        "category": args.category or "",
        "language": args.lang or "ru",
        "type": args.type or "direct",
    }

    job_id = db.create_ingestion_job("url", input_data)
    print(f"Created URL ingestion job #{job_id}")

    asyncio.run(run_job(job_id))
    job = db.get_ingestion_job(job_id)
    print(f"Job #{job_id} finished: {job['status']}")


def cmd_librivox(args):
    """Ingest from LibriVox."""
    from .. import db

    db.init_db()

    input_data = {"lang": args.lang, "limit": args.limit}
    job_id = db.create_ingestion_job("librivox", input_data)
    print(f"Created LibriVox ingestion job #{job_id} (lang={args.lang}, limit={args.limit})")


def cmd_archive(args):
    """Ingest from Archive.org."""
    from .. import db

    db.init_db()

    input_data = {"query": args.query, "limit": args.limit}
    job_id = db.create_ingestion_job("archive", input_data)
    print(f"Created Archive.org ingestion job #{job_id}")


def cmd_migrate(args):
    """Migrate existing books to new S3 layout."""
    from .. import db

    db.init_db()

    input_data = {"dry_run": args.dry_run}
    if args.book_id:
        input_data["book_id"] = args.book_id
    elif not args.all:
        print("Specify --all or --book-id N")
        sys.exit(1)

    job_id = db.create_ingestion_job("migrate", input_data)
    print(f"Created migration job #{job_id}" + (" (dry run)" if args.dry_run else ""))


def cmd_report(args):
    """Show ingestion report."""
    from .. import db

    db.init_db()

    conn = db._get_conn()
    days = args.days or 7
    stats = conn.execute(
        """
        SELECT status, COUNT(*) as cnt
        FROM ingestion_jobs
        WHERE created_at >= datetime('now', ?)
        GROUP BY status
    """,
        (f"-{days} days",),
    ).fetchall()
    print(f"Ingestion report (last {days} days):")
    print("-" * 30)
    total = 0
    for row in stats:
        print(f"  {row['status']:<12} {row['cnt']}")
        total += row["cnt"]
    print(f"  {'total':<12} {total}")


def main():
    """Main CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(prog="leerio-ingest", description="Content ingestion pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = sub.add_parser("status", help="Show job status")
    p_status.add_argument("--status", type=str, default=None)
    p_status.add_argument("--limit", type=int, default=20)
    p_status.set_defaults(func=cmd_status)

    # recover
    p_recover = sub.add_parser("recover", help="Recover stalled jobs")
    p_recover.set_defaults(func=cmd_recover)

    # retry
    p_retry = sub.add_parser("retry", help="Retry a failed job")
    p_retry.add_argument("--job-id", type=int, required=True)
    p_retry.set_defaults(func=cmd_retry)

    # normalize
    p_norm = sub.add_parser("normalize", help="Normalize existing books")
    p_norm.add_argument("--all", action="store_true")
    p_norm.add_argument("--book-id", type=int)
    p_norm.add_argument("--fast", action="store_true")
    p_norm.add_argument("--queue-only", action="store_true", help="Create job without running")
    p_norm.set_defaults(func=cmd_normalize)

    # url
    p_url = sub.add_parser("url", help="Ingest from URL")
    p_url.add_argument("url", type=str)
    p_url.add_argument("--title", type=str)
    p_url.add_argument("--author", type=str)
    p_url.add_argument("--reader", type=str, default="")
    p_url.add_argument("--category", type=str, default="")
    p_url.add_argument("--lang", type=str, default="ru")
    p_url.add_argument("--type", type=str, choices=["direct", "rss", "youtube"], default="direct")
    p_url.set_defaults(func=cmd_url)

    # librivox
    p_lv = sub.add_parser("librivox", help="Ingest from LibriVox")
    p_lv.add_argument("--lang", type=str, default="ru")
    p_lv.add_argument("--limit", type=int, default=50)
    p_lv.set_defaults(func=cmd_librivox)

    # archive
    p_ar = sub.add_parser("archive", help="Ingest from Archive.org")
    p_ar.add_argument("--query", type=str, default="audiobook russian")
    p_ar.add_argument("--limit", type=int, default=20)
    p_ar.set_defaults(func=cmd_archive)

    # migrate
    p_mig = sub.add_parser("migrate", help="Migrate to new S3 layout")
    p_mig.add_argument("--all", action="store_true")
    p_mig.add_argument("--book-id", type=int)
    p_mig.add_argument("--dry-run", action="store_true")
    p_mig.set_defaults(func=cmd_migrate)

    # report
    p_rep = sub.add_parser("report", help="Ingestion report")
    p_rep.add_argument("--days", type=int, default=7)
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
