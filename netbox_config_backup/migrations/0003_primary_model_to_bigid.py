# Generated by Django 3.2.8 on 2021-11-23 02:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0002_git_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='backup',
            name='created',
        ),
        migrations.RemoveField(
            model_name='backup',
            name='custom_field_data',
        ),
        migrations.RemoveField(
            model_name='backup',
            name='last_updated',
        ),
        migrations.RemoveField(
            model_name='backup',
            name='tags',
        ),
        migrations.RemoveField(
            model_name='backupcommit',
            name='created',
        ),
        migrations.RemoveField(
            model_name='backupcommit',
            name='custom_field_data',
        ),
        migrations.RemoveField(
            model_name='backupcommit',
            name='last_updated',
        ),
        migrations.RemoveField(
            model_name='backupcommit',
            name='tags',
        ),
    ]
