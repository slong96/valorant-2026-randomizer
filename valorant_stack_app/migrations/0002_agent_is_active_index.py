# Generated migration to add index on is_active field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('valorant_stack_app', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='agent',
            index=models.Index(fields=['is_active'], name='valorant_st_is_acti_idx'),
        ),
    ]
