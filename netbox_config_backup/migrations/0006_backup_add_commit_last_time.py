# Generated by Django 3.2.8 on 2021-11-23 17:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0005_commit_add_time_field'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backupcommit',
            name='backup',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commits', to='netbox_config_backup.backup'),
        ),
    ]
