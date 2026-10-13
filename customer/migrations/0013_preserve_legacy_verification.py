from django.db import migrations


def preserve(apps, schema_editor):
    User = apps.get_model('customer', 'CustomUser')
    Profile = apps.get_model('customer', 'CustomerProfile')
    # Existing active accounts predate selectable SMS onboarding.
    User.objects.filter(is_active=True, email__isnull=False).exclude(email='').update(email_verified=True)
    # Legacy contact phones were not independently verified. Require verification
    # before new orders rather than treating an entered phone as proof of possession.
    Profile.objects.filter(user__phone_verified=False).update(is_complete=False)


class Migration(migrations.Migration):
    dependencies = [('customer', '0012_customuser_email_verified_customuser_phone_verified_and_more')]
    operations = [migrations.RunPython(preserve, migrations.RunPython.noop)]
