# Generated by Django 4.1.7 on 2023-04-05 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_config_backup', '0011_alter_backup_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='backup',
            name='status',
            field=models.CharField(default='active', max_length=50),
        ),
    ]
