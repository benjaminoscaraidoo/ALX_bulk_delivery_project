from decimal import Decimal
from django.db import migrations


def seed(apps, schema_editor):
    tariff = apps.get_model('order', 'DistanceTariff')
    area = apps.get_model('order', 'DeliveryArea')
    for upper, charge in [('10', '35'), ('25', '50'), ('30', '60')]:
        tariff.objects.get_or_create(upper_km=Decimal(upper), defaults={'charge': Decimal(charge)})
    for name in ['Kumasi', 'Takoradi', 'Tamale']:
        area.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [('order', '0013_deliveryarea_distancetariff_package_delivery_address_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
