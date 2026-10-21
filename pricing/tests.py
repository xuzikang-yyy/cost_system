"""核价模型与关键业务场景测试。"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CostRule, Material, Part, Supplier, SupplierQuote
from .services import compute_cost, create_calculation, quote_metrics


class CostEngineTests(TestCase):
    def setUp(self):
        self.material = Material.objects.create(
            code="CU-T2", name="紫铜带 T2", material_type="铜", unit="千克"
        )
        self.part = Part.objects.create(
            code="CU-BUS-001", name="铜排支架", material=self.material,
            category="铜件", net_weight=Decimal("0.3200"),
        )
        self.rule = CostRule.objects.create(
            name="铜件标准规则", category="铜件", loss_rate=Decimal("2.50"),
            processing_fee=Decimal("1.80"), outsourcing_fee=Decimal("0.60"),
            packaging_fee=Decimal("0.15"), overhead_fee=Decimal("0.45"),
            scrap_price=Decimal("48.00"), markup_rate=Decimal("8.00"),
            deviation_low=Decimal("-8.00"), deviation_high=Decimal("8.00"),
        )
        self.user = User.objects.create_user("tester", password="pass12345")
        self.supplier = Supplier.objects.create(code="S1", name="测试供应商")

    def _values(self):
        return compute_cost(
            net_weight=Decimal("0.3200"), material_price=Decimal("62.50"),
            loss_rate=Decimal("2.50"), processing_fee=Decimal("1.80"),
            outsourcing_fee=Decimal("0.60"), packaging_fee=Decimal("0.15"),
            overhead_fee=Decimal("0.45"), scrap_price=Decimal("48.00"),
            markup_rate=Decimal("8.00"),
        )

    def test_material_input_and_cost(self):
        values = self._values()
        self.assertEqual(values["material_input_weight"], Decimal("0.3282"))
        self.assertEqual(values["material_cost"], Decimal("20.51"))

    def test_scrap_and_unit_cost(self):
        values = self._values()
        self.assertEqual(values["scrap_weight"], Decimal("0.0082"))
        self.assertEqual(values["scrap_recovery"], Decimal("0.39"))
        self.assertEqual(values["unit_cost"], Decimal("23.12"))
        self.assertEqual(values["reference_price"], Decimal("24.97"))

    def test_zero_loss_rate(self):
        values = compute_cost(
            net_weight=Decimal("1"), material_price=Decimal("10"), loss_rate=Decimal("0"),
            processing_fee=0, outsourcing_fee=0, packaging_fee=0, overhead_fee=0,
            scrap_price=0, markup_rate=0,
        )
        self.assertEqual(values["material_input_weight"], Decimal("1.0000"))
        self.assertEqual(values["unit_cost"], Decimal("10.00"))

    def test_invalid_loss_rate(self):
        with self.assertRaises(ValueError):
            compute_cost(
                net_weight=Decimal("1"), material_price=Decimal("10"), loss_rate=Decimal("100"),
                processing_fee=0, outsourcing_fee=0, packaging_fee=0, overhead_fee=0,
                scrap_price=0, markup_rate=0,
            )

    def test_quote_normalized_from_tax_included(self):
        quote = SupplierQuote.objects.create(
            supplier=self.supplier, part=self.part, unit_price=Decimal("28.25"),
            price_unit="件", tax_included=True, tax_rate=Decimal("13.00"),
        )
        self.assertEqual(quote.normalized_price, Decimal("25.0000"))

    def test_quote_normalized_from_usd_per_kg(self):
        quote = SupplierQuote.objects.create(
            supplier=self.supplier, part=self.part, unit_price=Decimal("4.00"),
            price_unit="千克", tax_included=False, currency="USD",
            exchange_rate=Decimal("7.1000"),
        )
        self.assertEqual(quote.normalized_price, Decimal("9.0880"))

    def test_quote_deviation_levels(self):
        calc = create_calculation(
            part=self.part, rule=self.rule, user=self.user,
            data={
                "net_weight": Decimal("0.3200"), "material_price": Decimal("62.50"),
                "loss_rate": Decimal("2.50"), "processing_fee": Decimal("1.80"),
                "outsourcing_fee": Decimal("0.60"), "packaging_fee": Decimal("0.15"),
                "overhead_fee": Decimal("0.45"), "scrap_price": Decimal("48.00"),
                "markup_rate": Decimal("8.00"), "price_date": timezone.localdate(),
            },
        )
        normal = SupplierQuote.objects.create(
            supplier=self.supplier, part=self.part, unit_price=Decimal("28.22"),
            tax_included=True, tax_rate=Decimal("13.00"),
        )
        high = SupplierQuote.objects.create(
            supplier=Supplier.objects.create(code="S2", name="高价供应商"),
            part=self.part, unit_price=Decimal("32.00"), quote_date=timezone.localdate(),
        )
        self.assertEqual(quote_metrics(normal, calc)["level"], "normal")
        self.assertEqual(quote_metrics(high, calc)["level"], "high")

    def test_high_quote_alert(self):
        calc = create_calculation(
            part=self.part, rule=self.rule, user=self.user,
            data={
                "net_weight": Decimal("0.3200"), "material_price": Decimal("62.50"),
                "loss_rate": Decimal("2.50"), "processing_fee": Decimal("1.80"),
                "outsourcing_fee": Decimal("0.60"), "packaging_fee": Decimal("0.15"),
                "overhead_fee": Decimal("0.45"), "scrap_price": Decimal("48.00"),
                "markup_rate": Decimal("8.00"), "price_date": timezone.localdate(),
            },
        )
        quote = SupplierQuote.objects.create(
            supplier=self.supplier, part=self.part, unit_price=Decimal("35.00"),
        )
        metric = quote_metrics(quote, calc)
        self.assertGreater(metric["rate"], Decimal("8"))

    def test_calculation_snapshot_keeps_parameters(self):
        calc = create_calculation(
            part=self.part, rule=self.rule, user=self.user,
            data={
                "net_weight": Decimal("0.3200"), "material_price": Decimal("62.50"),
                "loss_rate": Decimal("2.50"), "processing_fee": Decimal("1.80"),
                "outsourcing_fee": Decimal("0.60"), "packaging_fee": Decimal("0.15"),
                "overhead_fee": Decimal("0.45"), "scrap_price": Decimal("48.00"),
                "markup_rate": Decimal("8.00"), "price_date": timezone.localdate(),
            },
        )
        self.assertEqual(calc.material_price, Decimal("62.5000"))
        self.assertEqual(calc.details.count(), 6)
        self.assertEqual(calc.details.get(item_type="scrap").amount, Decimal("-0.39"))


class ViewAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="admin12345")
        self.buyer = User.objects.create_user("buyer", password="buyer12345")

    def test_login_required(self):
        response = self.client.get(reverse("pricing:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("pricing:login"), response.url)

    def test_buyer_cannot_manage_system(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("pricing:system"))
        self.assertEqual(response.status_code, 302)

    def test_buyer_can_create_calculation_page(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("pricing:calc_create"))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_open_dashboard(self):
        self.client.force_login(self.admin)
        for name in ["dashboard", "material_list", "part_list", "rule_list", "supplier_list",
                     "quote_list", "calc_list", "analysis", "system"]:
            response = self.client.get(reverse(f"pricing:{name}"))
            self.assertEqual(response.status_code, 200, name)
