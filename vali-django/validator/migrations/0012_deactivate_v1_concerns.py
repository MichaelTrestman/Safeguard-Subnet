# Data migration: flip every existing Concern row to `active=False`.
#
# Workstream 1 of the Concerns v2 redesign. v1 (landed in 0009) copied
# the legacy BaitPattern content into Concern rows with the wrong
# conceptual model — the JSONField-backed `detection_cues` and
# `example_prompts` collapsed several distinct ideas into one bag each,
# and the rows themselves described user-side bait patterns rather than
# first-person operator worries about AI behavior.
#
# The operator has explicitly chosen to FLUSH the v1 content rather
# than parse it into the new DetectionCue / UserTrigger tables. v1
# rows become history-only: they stay in the DB so any currently-
# running code referencing them doesn't crash during rollout, but the
# `/api/concerns` endpoint (which filters by `active=True`) stops
# serving them. Operators hand-author new v2 concerns through the
# curation UI after Workstream 2 lands.
#
# No reverse — a rollback would re-activate rows whose content no
# longer matches the v2 model, which is worse than a one-way flip.

from django.db import migrations


def deactivate_v1_concerns(apps, schema_editor):
    Concern = apps.get_model("validator", "Concern")
    # All concerns authored before v2 (everything currently in the DB)
    # are marked inactive and become history-only. Operators hand-author
    # new concerns through the curation UI after Workstream 2 lands. Do
    # NOT attempt to parse the JSONField contents — they describe the
    # old bait-pattern conceptual model and are unreliable for v2.
    n = Concern.objects.filter(active=True).update(active=False)
    print(f"[0012_deactivate_v1_concerns] marked {n} v1 concerns inactive")


class Migration(migrations.Migration):

    dependencies = [
        ('validator', '0011_detection_cue_user_trigger_finding_matched_cues'),
    ]

    operations = [
        migrations.RunPython(deactivate_v1_concerns, migrations.RunPython.noop),
    ]
