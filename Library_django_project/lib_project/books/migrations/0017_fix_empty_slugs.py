from django.db import migrations
from django.utils.text import slugify

def fix_empty_slugs(apps, schema_editor):
    Collection = apps.get_model('books', 'Collection')
    for collection in Collection.objects.filter(slug=''):
        base_slug = slugify(collection.title)
        slug = base_slug
        counter = 1
        while Collection.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        collection.slug = slug
        collection.save()

class Migration(migrations.Migration):
    dependencies = [
        ('books', '0016_remove_collection_featured_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_empty_slugs, reverse_code=migrations.RunPython.noop),
    ] 