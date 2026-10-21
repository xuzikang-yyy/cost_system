"""生成演示数据：材料价格、零件、成本规则、供应商、历史核价与报价。"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pricing.models import (
    CostCalculation,
    CostRule,
    Material,
    MaterialPrice,
    Part,
    Supplier,
    SupplierQuote,
    SystemSetting,
)
from pricing.services import active_rule, create_calculation, price_on, q2

random.seed(20261020)


def month_first(base, months_back):
    year = base.year
    month = base.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def aware(day, hour=10, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class Command(BaseCommand):
    help = "生成演示数据（幂等：已有数据时跳过）"

    def handle(self, *args, **options):
        if Material.objects.exists() or CostCalculation.objects.exists():
            self.stdout.write(self.style.WARNING("已存在业务数据，跳过演示数据生成。"))
            return
        with transaction.atomic():
            self._seed()

    def _seed(self):
        today = timezone.localdate()
        random.seed(20261020)

        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"first_name": "周明", "email": "admin@example.com"},
        )
        admin.is_superuser = True
        admin.is_staff = True
        admin.first_name = "周明"
        admin.set_password("admin123")
        admin.save()

        buyer, _ = User.objects.get_or_create(
            username="buyer",
            defaults={"first_name": "李婧"},
        )
        buyer.is_superuser = False
        buyer.is_staff = False
        buyer.first_name = "李婧"
        buyer.set_password("buyer123")
        buyer.save()

        setting = SystemSetting.load()
        setting.company_name = "采购成本核价中心"
        setting.save()

        material_specs = [
            ("CU-T2", "紫铜带 T2", "铜", "千克", "0.8×200mm 卷料", "62.50"),
            ("AL-6061", "铝板 6061-T6", "铝", "千克", "2.0×1219×2438mm", "20.80"),
            ("ABS-757", "ABS 塑料粒子", "塑料", "千克", "757 本色", "12.60"),
            ("ST-SPCC", "冷轧钢 SPCC", "钢", "千克", "1.0×1250mm 卷料", "5.40"),
        ]
        materials = {}
        for code, name, kind, unit, spec, base_price in material_specs:
            material = Material.objects.create(
                code=code, name=name, material_type=kind, unit=unit,
                specification=spec, remark="演示数据",
            )
            materials[code] = material
            for index in range(12, -1, -1):
                point = month_first(today, index)
                wave = Decimal(str(round(random.uniform(-0.035, 0.035), 4)))
                trend = Decimal(str(index)) * Decimal("0.004")
                price = Decimal(base_price) * (Decimal("1") - trend + wave)
                price = price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                MaterialPrice.objects.create(
                    material=material,
                    price=price,
                    effective_date=point,
                    source="长江有色" if kind in ("铜", "铝") else "供应商报价",
                )

        part_specs = [
            ("CU-BUS-001", "铜排支架", "CU-T2", "铜件", "80×60×3mm", "0.3200", "T2-2024-031"),
            ("CU-CON-014", "接线端子", "CU-T2", "铜件", "M8 双孔", "0.0850", "T2-2024-114"),
            ("AL-BRK-207", "铝制安装支架", "AL-6061", "铝件", "L 型 180×90×4mm", "0.4600", "AL-2024-207"),
            ("AL-HSK-031", "散热片", "AL-6061", "铝件", "120×80×18mm", "0.1850", "AL-2024-031"),
            ("PL-CVR-102", "控制器上盖", "ABS-757", "塑料件", "186×126×24mm", "0.1260", "PL-2024-102"),
            ("PL-BSE-105", "控制器底座", "ABS-757", "塑料件", "186×126×18mm", "0.1580", "PL-2024-105"),
            ("ST-BRA-330", "钢制加强板", "ST-SPCC", "其他", "260×40×2mm", "0.7800", "ST-2024-330"),
        ]
        parts = {}
        for code, name, material_code, category, spec, weight, drawing in part_specs:
            part = Part.objects.create(
                code=code, name=name, material=materials[material_code], category=category,
                specification=spec, net_weight=Decimal(weight), drawing_no=drawing,
            )
            parts[code] = part

        rule_specs = [
            ("铜件标准成本规则 V2.1", "铜件", "2.50", "1.80", "0.60", "0.15", "0.45",
             "48.00", "8.00", "-8.00", "8.00", "V2.1", "含电镀表面处理，废料按紫铜回收价"),
            ("铝件标准成本规则 V1.4", "铝件", "3.50", "1.20", "0.85", "0.18", "0.35",
             "13.50", "7.50", "-8.00", "8.00", "V1.4", "含阳极氧化，按型材利用率核算损耗"),
            ("塑料件成本规则 V3.0", "塑料件", "4.50", "0.65", "0.00", "0.12", "0.22",
             "2.50", "9.00", "-10.00", "10.00", "V3.0", "注塑件，含色母与包装分摊"),
            ("钢制件成本规则 V1.2", "其他", "3.00", "0.90", "0.40", "0.20", "0.30",
             "2.20", "7.00", "-8.00", "8.00", "V1.2", "冲压件，含防锈处理"),
        ]
        for name, category, loss, processing, outsourcing, packaging, overhead, scrap, markup, low, high, version, remark in rule_specs:
            CostRule.objects.create(
                name=name, category=category, loss_rate=Decimal(loss),
                processing_fee=Decimal(processing), outsourcing_fee=Decimal(outsourcing),
                packaging_fee=Decimal(packaging), overhead_fee=Decimal(overhead),
                scrap_price=Decimal(scrap), markup_rate=Decimal(markup),
                deviation_low=Decimal(low), deviation_high=Decimal(high),
                version=version, effective_date=month_first(today, 12), remark=remark,
            )

        supplier_specs = [
            ("SUP-001", "苏州华铜精密制造有限公司", "铜件", "王立新", "138-0621-4520", "合格"),
            ("SUP-002", "宁波精益金属制品有限公司", "铜件", "陈静", "137-7712-8834", "合格"),
            ("SUP-003", "常州恒达铜业有限公司", "铜件", "刘建平", "139-6128-2201", "观察"),
            ("SUP-004", "昆山铝拓精密科技有限公司", "铝件", "张慧", "159-5082-7716", "合格"),
            ("SUP-005", "无锡鸿泰铝制品厂", "铝件", "周晓东", "136-2517-6620", "合格"),
            ("SUP-006", "东莞联塑精密模具有限公司", "塑料件", "何志强", "135-8031-4472", "合格"),
            ("SUP-007", "深圳宏塑科技有限公司", "塑料件", "李欣", "158-1934-9056", "观察"),
            ("SUP-008", "上海远航五金制造有限公司", "综合", "赵磊", "137-6482-3390", "合格"),
        ]
        suppliers = {}
        for code, name, category, contact, phone, status in supplier_specs:
            supplier = Supplier.objects.create(
                code=code, name=name, category=category, contact=contact, phone=phone, status=status
            )
            suppliers[code] = supplier

        # 历史核价：每行（零件编号, 距今天数, 核价人）
        calc_plan = [
            ("CU-BUS-001", 120, admin), ("CU-BUS-001", 62, buyer), ("CU-BUS-001", 8, buyer),
            ("CU-CON-014", 96, admin), ("CU-CON-014", 20, buyer),
            ("AL-BRK-207", 133, buyer), ("AL-BRK-207", 47, admin), ("AL-BRK-207", 6, buyer),
            ("AL-HSK-031", 88, admin), ("AL-HSK-031", 12, buyer),
            ("PL-CVR-102", 110, buyer), ("PL-CVR-102", 41, buyer), ("PL-CVR-102", 4, buyer),
            ("PL-BSE-105", 73, admin), ("PL-BSE-105", 15, buyer),
            ("ST-BRA-330", 28, admin),
        ]
        counter = {}
        for code, days_ago, user in calc_plan:
            part = parts[code]
            calc_date = today - timedelta(days=days_ago)
            rule = active_rule(part, calc_date)
            price = price_on(part.material, calc_date)
            stamp = calc_date.strftime("%Y%m%d")
            counter[stamp] = counter.get(stamp, 0) + 1
            calc_no = f"HJ{stamp}{counter[stamp]:03d}"

            calc = create_calculation(
                part=part,
                rule=rule,
                user=user,
                data={
                    "net_weight": part.net_weight,
                    "material_price": price.price,
                    "loss_rate": rule.loss_rate,
                    "processing_fee": rule.processing_fee,
                    "outsourcing_fee": rule.outsourcing_fee,
                    "packaging_fee": rule.packaging_fee,
                    "overhead_fee": rule.overhead_fee,
                    "scrap_price": rule.scrap_price,
                    "markup_rate": rule.markup_rate,
                    "price_date": price.effective_date,
                },
                status="confirmed",
                remark="演示核价数据",
            )
            CostCalculation.objects.filter(pk=calc.pk).update(
                calc_no=calc_no,
                created_at=aware(calc_date, hour=9 + (counter[stamp] % 8), minute=20),
            )

        # 报价：目标偏差（%），部分使用美元 / 元每千克 / 不含税口径
        quote_plan = {
            "CU-BUS-001": [
                ("SUP-001", "-1.8", "件", True, "CNY", 12),
                ("SUP-002", "2.4", "件", True, "USD", 15),
                ("SUP-003", "13.5", "件", True, "CNY", 18),
                ("SUP-008", "-11.2", "件", True, "CNY", 10),
            ],
            "CU-CON-014": [
                ("SUP-001", "3.1", "件", True, "CNY", 12),
                ("SUP-002", "-4.6", "件", True, "CNY", 14),
                ("SUP-003", "9.8", "件", True, "CNY", 20),
            ],
            "AL-BRK-207": [
                ("SUP-004", "-1.2", "件", True, "CNY", 14),
                ("SUP-005", "2.8", "千克", True, "CNY", 12),
                ("SUP-008", "14.0", "件", True, "CNY", 18),
            ],
            "AL-HSK-031": [
                ("SUP-004", "4.2", "件", True, "CNY", 13),
                ("SUP-005", "-6.1", "件", True, "CNY", 11),
                ("SUP-008", "8.4", "件", True, "CNY", 16),
            ],
            "PL-CVR-102": [
                ("SUP-006", "1.5", "件", True, "CNY", 10),
                ("SUP-007", "-12.4", "件", False, "CNY", 12),
            ],
            "PL-BSE-105": [
                ("SUP-006", "-2.2", "件", True, "CNY", 10),
                ("SUP-007", "6.9", "件", True, "CNY", 12),
                ("SUP-008", "11.3", "件", True, "CNY", 15),
            ],
            "ST-BRA-330": [
                ("SUP-008", "2.0", "件", True, "CNY", 15),
                ("SUP-001", "7.5", "件", True, "CNY", 18),
            ],
        }

        for code, rows in quote_plan.items():
            part = parts[code]
            calc = part.calculations.filter(status="confirmed").order_by("-created_at").first()
            reference = calc.reference_price
            for index, (supplier_code, deviation, unit, tax_included, currency, lead) in enumerate(rows):
                normalized = q2(reference * (Decimal("1") + Decimal(deviation) / Decimal("100")))
                gross = normalized
                if tax_included:
                    gross = gross * Decimal("1.13")
                if unit == "千克":
                    gross = gross / part.net_weight
                if currency == "USD":
                    gross = gross / Decimal("7.10")
                raw = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                quote_date = today - timedelta(days=3 + index * 4)
                SupplierQuote.objects.create(
                    supplier=suppliers[supplier_code],
                    part=part,
                    unit_price=raw,
                    price_unit=unit,
                    quote_date=quote_date,
                    tax_included=tax_included,
                    tax_rate=Decimal("13.00"),
                    currency=currency,
                    exchange_rate=Decimal("7.1000") if currency == "USD" else Decimal("1.0000"),
                    lead_time_days=lead,
                    remark="演示报价",
                )

        self.stdout.write(self.style.SUCCESS(
            f"演示数据生成完成：{Material.objects.count()} 种材料、{Part.objects.count()} 个零件、"
            f"{SupplierQuote.objects.count()} 条报价、{CostCalculation.objects.count()} 张核价单。"
        ))
