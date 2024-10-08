# Generated by Django 5.0.8 on 2024-10-01 23:44

import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0121_customfield_related_object_filter'),
        ('netbox_config_backup', '0017_add_job_to_backupjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='backupjob',
            name='custom_field_data',
            field=models.JSONField(
                blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder
            ),
        ),
        migrations.AddField(
            model_name='backupjob',
            name='last_updated',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='backupjob',
            name='tags',
            field=taggit.managers.TaggableManager(
                through='extras.TaggedItem', to='extras.Tag'
            ),
        ),
        migrations.AlterField(
            model_name='backupjob',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False
            ),
        ),
    ]
