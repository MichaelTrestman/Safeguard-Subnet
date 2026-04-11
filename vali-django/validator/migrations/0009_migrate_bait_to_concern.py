# Data migration: copy every BaitPattern row into a matching Concern row.
#
# Workstream B of the Concerns model migration (plan:
# /Users/michaeltrestman/.claude/plans/linear-leaping-stonebraker.md).
# DESIGN.md §2 "Concerns, curated by validators" makes Concern the
# first-class artifact; BaitPattern stays in place for one release as
# a read-only back-compat alias.
#
# Mapping:
#   id_slug          -> id_slug (preserved unchanged)
#   title            -> title
#   description      -> concern_text
#   detection_cues   -> detection_cues
#   example_prompts  -> example_prompts
#   category         -> category
#   severity (str)   -> severity_prior (float) via SEVERITY_TO_PRIOR
#
# Initialized:
#   version = 1
#   active = True
#   curator_hotkey = ""
#   curator_user = None
#
# The severity-code -> float mapping is deterministic. Unknown codes
# fall back to 0.5 with a printed warning (no raise — the migration
# must be resilient against hand-written or third-party BaitPattern
# rows that may have slipped in outside the seed migration).

from django.db import migrations


SEVERITY_TO_PRIOR: dict[str, float] = {
    # Content-safety (C#), High-severity (H#), Safety-ops (S#) code
    # families from bait/library.json. Tier 4 -> 0.8, 3 -> 0.7,
    # 2 -> 0.6, 1 -> 0.5. Unknown -> 0.5 (neutral prior).
    "C4": 0.8, "C3": 0.7, "C2": 0.6, "C1": 0.5,
    "H4": 0.8, "H3": 0.7, "H2": 0.6, "H1": 0.5,
    "S4": 0.8, "S3": 0.7, "S2": 0.6, "S1": 0.5,
}


def copy_bait_to_concern(apps, schema_editor):
    BaitPattern = apps.get_model("validator", "BaitPattern")
    Concern = apps.get_model("validator", "Concern")

    copied = 0
    for row in BaitPattern.objects.all():
        code = (row.severity or "").strip().upper()
        prior = SEVERITY_TO_PRIOR.get(code)
        if prior is None:
            print(
                f"[0009_migrate_bait_to_concern] unknown severity "
                f"code {row.severity!r} on {row.id_slug!r}; "
                f"defaulting severity_prior=0.5"
            )
            prior = 0.5

        # get_or_create on id_slug so re-running the migration (or
        # running on a DB where a Concern row already happens to
        # exist under the same slug) is idempotent.
        Concern.objects.get_or_create(
            id_slug=row.id_slug,
            defaults={
                "version": 1,
                "curator_hotkey": "",
                "curator_user": None,
                "active": True,
                "title": row.title,
                "concern_text": row.description or "",
                "detection_cues": list(row.detection_cues or []),
                "example_prompts": list(row.example_prompts or []),
                "category": row.category,
                "severity_prior": prior,
            },
        )
        copied += 1

    print(
        f"[0009_migrate_bait_to_concern] copied {copied} BaitPattern "
        f"rows into Concern"
    )


def delete_concern_rows(apps, schema_editor):
    """Reverse: drop every Concern row that was copied from a BaitPattern.

    We key on id_slug matches — anything added via the concern UI
    with a slug that doesn't exist in BaitPattern stays intact. In
    practice the reverse migration is only used during local dev
    rollback; a real prod rollback would use a DB snapshot.
    """
    BaitPattern = apps.get_model("validator", "BaitPattern")
    Concern = apps.get_model("validator", "Concern")

    bait_slugs = set(BaitPattern.objects.values_list("id_slug", flat=True))
    Concern.objects.filter(id_slug__in=bait_slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("validator", "0008_concern_registeredtarget_concerns_concernrevision"),
    ]

    operations = [
        migrations.RunPython(copy_bait_to_concern, delete_concern_rows),
    ]
