# Generated by Django 5.0.8 on 2024-09-06 02:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0013_backup__to_netboxmodel'),
    ]

    operations = [
        migrations.AddField(
            model_name='backup',
            name='config_status',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]