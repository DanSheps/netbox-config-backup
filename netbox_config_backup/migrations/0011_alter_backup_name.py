# Generated by Django 4.0.3 on 2022-04-14 15:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0010_backup_ip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backup',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]