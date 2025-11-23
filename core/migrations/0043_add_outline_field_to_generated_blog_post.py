# Generated manually for two-phase AI writing agent

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_autosubmissionsetting_deleted_at_blogpost_deleted_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedblogpost',
            name='outline',
            field=models.JSONField(
                blank=True,
                help_text='Structured outline used to generate the blog post content',
                null=True,
            ),
        ),
    ]
