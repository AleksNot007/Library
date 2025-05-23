from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('books', '0004_merge_0002_add_is_approved_0003_quote'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='submitted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='submitted_books',
                to='users.user',
                verbose_name='Добавил пользователь'
            ),
        ),
    ] 