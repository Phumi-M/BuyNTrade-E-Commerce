from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0013_listingimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="bio",
            field=models.TextField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_photo",
            field=models.ImageField(blank=True, null=True, upload_to="profiles/"),
        ),
    ]
