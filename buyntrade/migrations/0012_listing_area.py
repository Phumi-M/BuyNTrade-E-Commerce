from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0011_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="area",
            field=models.CharField(blank=True, help_text="City or suburb for local buy/trade", max_length=64),
        ),
    ]
