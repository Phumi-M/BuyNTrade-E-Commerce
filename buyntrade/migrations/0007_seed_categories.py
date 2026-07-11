from django.db import migrations


CATEGORY_NAMES = [
    "Electronics",
    "Appliances",
    "Fashion & Clothing",
    "Sports & Outdoors",
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("buyntrade", "Category")
    for name in CATEGORY_NAMES:
        Category.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0006_communitypost"),
    ]

    operations = [
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
