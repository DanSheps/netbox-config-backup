# Generated by Django 5.0.8 on 2024-10-01 01:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_job_object_type_optional'),
        ('netbox_config_backup', '0016_add_pid_to_backup_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='backupjob',
            name='runner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='backup_job',
                to='core.job',
            ),
        ),
    ]
