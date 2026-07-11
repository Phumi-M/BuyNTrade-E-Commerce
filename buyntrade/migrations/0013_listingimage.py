from django.db import migrations, models
import django.db.models.deletion


def copy_existing_listing_images(apps, schema_editor):
    Listing = apps.get_model("buyntrade", "Listing")
    ListingImage = apps.get_model("buyntrade", "ListingImage")

    for listing in Listing.objects.all():
        if listing.image and not ListingImage.objects.filter(listing_id=listing.id).exists():
            ListingImage.objects.create(
                listing=listing,
                image=listing.image,
                order=0,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0012_listing_area"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="listings/gallery/")),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gallery_images", to="buyntrade.listing")),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(copy_existing_listing_images, migrations.RunPython.noop),
    ]
