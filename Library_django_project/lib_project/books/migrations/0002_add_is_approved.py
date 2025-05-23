from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('books', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='is_approved',
            field=models.BooleanField(default=False, verbose_name='Одобрено модератором'),
        ),
    ] 