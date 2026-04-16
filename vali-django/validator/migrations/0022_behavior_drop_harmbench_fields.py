"""
Drop HarmBench-specific fields from Behavior that don't apply to the new
declarative-behavior model: context_string, functional_category, semantic_category.
Also flip active default to True (new behaviors are active by default).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("validator", "0021_behaviorclassification"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="behavior",
            name="context_string",
        ),
        migrations.RemoveField(
            model_name="behavior",
            name="functional_category",
        ),
        migrations.RemoveField(
            model_name="behavior",
            name="semantic_category",
        ),
        migrations.AlterField(
            model_name="behavior",
            name="active",
            field=models.BooleanField(
                default=True,
                db_index=True,
                help_text="Active behaviors are served to miners and used by the classifier.",
            ),
        ),
        migrations.AlterModelOptions(
            name="behavior",
            options={"ordering": ["source_ref"]},
        ),
    ]
