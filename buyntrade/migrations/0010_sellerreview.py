from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0009_listing_media_uploads"),
    ]

    operations = [
        migrations.CreateModel(
            name="SellerReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField()),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seller_reviews", to="buyntrade.listing")),
                ("reviewer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews_given", to="buyntrade.user")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seller_reviews", to="buyntrade.user")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="sellerreview",
            constraint=models.UniqueConstraint(fields=("reviewer", "listing"), name="unique_review_per_listing"),
        ),
    ]
