# Generated by Django 3.2.4 on 2023-07-25 14:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tr_ars', '0009_auto_20230622_2015'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='merged_versions_list',
            field=models.JSONField(null=True, verbose_name='Ordered list of merged_version PKs'),
        ),
    ]
