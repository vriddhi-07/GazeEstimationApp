from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("survey_app", "0010_movie_target_groups_networkdiagram_target_groups_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="participantsession",
            name="expertise_sentiment",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="participantsession",
            name="expertise_fakenews",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="participantsession",
            name="expertise_visualisation",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="participantsession",
            name="expertise_completed_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]