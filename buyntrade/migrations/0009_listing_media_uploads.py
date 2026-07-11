from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0008_listing_ends_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="listings/images/"),
        ),
        migrations.AddField(
            model_name="listing",
            name="video",
            field=models.FileField(blank=True, null=True, upload_to="listings/videos/"),
        ),
        migrations.AddField(
            model_name="listing",
            name="video_thumbnail",
            field=models.ImageField(blank=True, null=True, upload_to="listings/thumbnails/"),
        ),
    ]
