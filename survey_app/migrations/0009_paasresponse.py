from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("survey_app", "0008_networkdiagram_image_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaasResponse",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("task_number", models.PositiveSmallIntegerField()),
                ("rating", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="paas_responses",
                        to="survey_app.participantsession",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["participant", "task_number"],
                        name="unique_paas_per_task_participant",
                    )
                ],
            },
        ),
    ]
