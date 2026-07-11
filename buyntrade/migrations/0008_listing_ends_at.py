from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def set_default_ends_at(apps, schema_editor):
    Listing = apps.get_model("buyntrade", "Listing")
    default_end = timezone.now() + timedelta(days=7)
    Listing.objects.filter(ends_at__isnull=True).update(ends_at=default_end)


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0007_seed_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(set_default_ends_at, migrations.RunPython.noop),
    ]
