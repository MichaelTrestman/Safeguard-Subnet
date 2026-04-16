from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('validator', '0023_widen_classifier_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='registeredtarget',
            name='active',
            field=models.BooleanField(
                default=True,
                db_index=True,
                help_text='Inactive targets receive no new probes and are hidden from public views. Historical data is preserved.',
            ),
        ),
    ]
