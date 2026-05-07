from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("validator", "0024_registeredtarget_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="audit_reasoning",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="evaluation",
            name="miner_rationale",
            field=models.TextField(blank=True, default=""),
        ),
    ]
