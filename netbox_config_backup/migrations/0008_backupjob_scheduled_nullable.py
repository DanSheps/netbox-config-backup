# Generated by Django 3.2.8 on 2021-11-23 18:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0007_backup_job_add_scheduled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backupjob',
            name='scheduled',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
