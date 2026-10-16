from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tr_ars', '0014_auto_20250121_2122'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='received_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name="time the agent's response was received"),
        ),
    ]