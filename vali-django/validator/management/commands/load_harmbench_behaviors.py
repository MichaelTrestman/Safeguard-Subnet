"""
Load HarmBench behaviors from a JSON file (produced by
tmp-scripts/ingest_harmbench_behaviors.py) into the validator's
Concern and Behavior tables.

Usage:
    python manage.py load_harmbench_behaviors --file /tmp/harmbench.json

Idempotent: source_ref (Behavior) and id_slug (Concern) are the natural
keys. Re-running with the same file is safe and preserves operator state:

- Concerns are get_or_create'd by id_slug. Existing Concerns are reused
  as-is (no overwrite of title/concern_text/active). Missing Concerns
  are created with active=False. The JSON's kind field ('existing' vs
  'new') is informational — it records what the ingestion run expected
  to find, but is not enforced.
- Behaviors are upserted by source_ref. On re-run, behavior_text /
  context_string / functional_category / semantic_category are updated
  from the JSON; `active` is NEVER overwritten (we will not silently
  deactivate a behavior the operator activated previously).
- M2M associations (Behavior.concerns) are merged additively — operator
  associations are preserved.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from validator.models import Behavior, Concern


class Command(BaseCommand):
    help = "Load HarmBench behaviors from an ingested JSON file into the DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            required=True,
            help="Path to the JSON file produced by ingest_harmbench_behaviors.py",
        )

    def handle(self, *args, **options):
        path: Path = options["file"]
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        data = json.loads(path.read_text())

        # Pass 1: ensure all referenced Concerns exist (get_or_create for all)
        concerns_by_slug: dict[str, Concern] = {}
        concerns_created = 0
        concerns_found = 0
        for c in data.get("concerns", []):
            slug = c["id_slug"]
            obj, created = Concern.objects.get_or_create(
                id_slug=slug,
                defaults={
                    "title": c.get("title") or slug,
                    "concern_text": c.get("concern_text") or "",
                    # If the JSON expected an existing concern and it wasn't
                    # there, tag the auto-created one as harmbench-sourced so
                    # operator can tell it apart from ones they authored.
                    "category": "harmbench" if c.get("kind") == "new" else "harmbench-auto",
                    "active": False,
                },
            )
            if created:
                concerns_created += 1
            else:
                concerns_found += 1
            concerns_by_slug[slug] = obj

        # Pass 2: upsert behaviors + merge M2M associations
        behaviors_created = 0
        behaviors_updated = 0
        associations_added = 0

        with transaction.atomic():
            for b in data.get("behaviors", []):
                behavior, created = Behavior.objects.update_or_create(
                    source_ref=b["source_ref"],
                    defaults={
                        "behavior_text": b["behavior_text"],
                        "context_string": b.get("context_string", ""),
                        "functional_category": b.get("functional_category", "standard"),
                        "semantic_category": b.get("semantic_category", ""),
                        # NOTE: deliberately NOT updating `active` on re-run —
                        # respect operator activation state.
                    },
                )
                if created:
                    behaviors_created += 1
                    # Only set active=False explicitly on first creation.
                    if behavior.active:
                        behavior.active = False
                        behavior.save(update_fields=["active"])
                else:
                    behaviors_updated += 1

                existing_slugs = set(
                    behavior.concerns.values_list("id_slug", flat=True)
                )
                for slug in b.get("concerns", []):
                    if slug in existing_slugs:
                        continue
                    concern = concerns_by_slug.get(slug)
                    if concern is None:
                        raise CommandError(
                            f"Behavior '{b['source_ref']}' references concern "
                            f"'{slug}' which is not in the JSON's concerns list."
                        )
                    behavior.concerns.add(concern)
                    associations_added += 1

        self.stdout.write(self.style.SUCCESS(
            f"Concerns: {concerns_created} created, {concerns_found} already present"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Behaviors: {behaviors_created} created, {behaviors_updated} updated"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Concern associations: {associations_added} added"
        ))
