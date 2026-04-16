"""
Re-audit Evaluation rows that have a null audit_score.

These are created when the audit pipeline crashes mid-transaction (leaving
the Evaluation row persisted but without scores), or when an eval was
dispatched during an outage and never fully processed.

Usage:
    python manage.py reaudit_evals
    python manage.py reaudit_evals --limit 50
    python manage.py reaudit_evals --task-id <task_id>
    python manage.py reaudit_evals --dry-run

Idempotent: already-audited rows (audit_score not null) are skipped by
_audit_one_evaluation. BehaviorClassification rows use ignore_conflicts so
re-running is safe.
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("vali.management")


class Command(BaseCommand):
    help = "Re-audit Evaluation rows with null audit_score"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max rows to process (0 = all)",
        )
        parser.add_argument(
            "--task-id",
            type=str,
            default="",
            help="Re-audit a single evaluation by task_id",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be re-audited without writing anything",
        )

    def handle(self, *args, **options):
        from validator.models import Evaluation
        from validator.loop import _audit_one_evaluation
        from validator.audit import load_default_bait_library

        # _audit_one_evaluation is decorated with @sync_to_async for use
        # in the async loop. Unwrap it to call synchronously here.
        _audit_one_evaluation_sync = getattr(_audit_one_evaluation, "__wrapped__", _audit_one_evaluation)

        dry_run = options["dry_run"]
        limit = options["limit"]
        task_id = options["task_id"]

        if task_id:
            qs = Evaluation.objects.filter(task_id=task_id)
        else:
            qs = (
                Evaluation.objects
                .filter(audit_score__isnull=True)
                .exclude(transcript=[])
                .order_by("timestamp")
            )

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Found {total} evaluation(s) to re-audit")

        if dry_run:
            for e in qs:
                self.stdout.write(
                    f"  DRY-RUN {e.task_id[:12]} miner={e.miner_uid} "
                    f"concern={e.concern_id_slug}"
                )
            return

        bait_library = load_default_bait_library()

        done = 0
        skipped = 0
        errors = 0
        for eval_row in qs:
            try:
                result = _audit_one_evaluation_sync(eval_row.task_id, bait_library)
                if result and result.get("skipped"):
                    skipped += 1
                else:
                    done += 1
                    if result:
                        self.stdout.write(
                            f"  OK {eval_row.task_id[:12]} miner={eval_row.miner_uid} "
                            f"audit={result.get('audit_score', '?')} "
                            f"accepted={result.get('accepted_severity', '?')}"
                        )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"  ERR {eval_row.task_id[:12]}: {e}")
                )

        self.stdout.write(
            f"\nDone: {done} re-audited, {skipped} already audited (skipped), {errors} errors"
        )
