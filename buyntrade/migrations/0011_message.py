from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("buyntrade", "0010_sellerreview"),
    ]

    operations = [
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="buyntrade.listing")),
                ("receiver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_messages", to="buyntrade.user")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_messages", to="buyntrade.user")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
