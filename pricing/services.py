"""核价业务规则：成本计算、报价偏差、历史快照。

所有金额均以人民币、不含税口径保存；供应商报价在比较前
统一换算为「元/件、不含税、人民币」，避免口径不一致导致误判。
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count
from django.utils import timezone

from .models import CostCalculation, CostCalculationDetail, CostRule, MaterialPrice, SupplierQuote

TWO = Decimal("0.01")
FOUR = Decimal("0.0001")


def q2(value):
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def q4(value):
    return Decimal(value or 0).quantize(FOUR, rounding=ROUND_HALF_UP)


def active_rule(part, on_date=None):
    """按零件类别取当前生效的成本规则（最新生效版本）。"""
    on_date = on_date or timezone.localdate()
    return (
        CostRule.objects.filter(
            category=part.category, is_active=True, effective_date__lte=on_date
        )
        .order_by("-effective_date", "-id")
        .first()
    )


def price_on(material, on_date=None):
    """取指定日期前最近一次材料价格。"""
    on_date = on_date or timezone.localdate()
    return (
        MaterialPrice.objects.filter(material=material, effective_date__lte=on_date)
        .order_by("-effective_date", "-id")
        .first()
    )


def compute_cost(*, net_weight, material_price, loss_rate, processing_fee, outsourcing_fee,
                 packaging_fee, overhead_fee, scrap_price, markup_rate):
    """核心成本模型。

    材料投入量 = 成品净重 / (1 - 损耗率)
    材料成本   = 材料投入量 × 材料单价
    废料回收   = (材料投入量 - 成品净重) × 废料单价
    理论成本   = 材料成本 + 加工费 + 外协费 + 包装物流 + 制造费用 - 废料回收
    参考报价   = 理论成本 × (1 + 合理加成率)
    """
    net_weight = Decimal(net_weight or 0)
    material_price = Decimal(material_price or 0)
    loss_rate = Decimal(loss_rate or 0)
    rate = loss_rate / Decimal("100")

    if net_weight <= 0:
        raise ValueError("成品净重必须大于 0")
    if material_price < 0:
        raise ValueError("材料单价不能为负数")
    if rate < 0 or rate >= 1:
        raise ValueError("损耗率必须在 0% 到 100% 之间")

    input_weight = q4(net_weight / (Decimal("1") - rate))
    material_cost = q2(input_weight * material_price)
    scrap_weight = q4(max(input_weight - net_weight, Decimal("0")))
    scrap_recovery = q2(scrap_weight * Decimal(scrap_price or 0))
    unit_cost = q2(
        material_cost
        + Decimal(processing_fee or 0)
        + Decimal(outsourcing_fee or 0)
        + Decimal(packaging_fee or 0)
        + Decimal(overhead_fee or 0)
        - scrap_recovery
    )
    reference_price = q2(unit_cost * (Decimal("1") + Decimal(markup_rate or 0) / Decimal("100")))

    return {
        "net_weight": q4(net_weight),
        "material_price": q4(material_price),
        "loss_rate": q2(loss_rate),
        "material_input_weight": input_weight,
        "material_cost": material_cost,
        "processing_fee": q2(processing_fee),
        "outsourcing_fee": q2(outsourcing_fee),
        "packaging_fee": q2(packaging_fee),
        "overhead_fee": q2(overhead_fee),
        "scrap_weight": scrap_weight,
        "scrap_price": q2(scrap_price),
        "scrap_recovery": scrap_recovery,
        "unit_cost": unit_cost,
        "markup_rate": q2(markup_rate),
        "reference_price": reference_price,
    }


def next_calc_no():
    prefix = timezone.localdate().strftime("HJ%Y%m%d")
    last = (
        CostCalculation.objects.filter(calc_no__startswith=prefix)
        .order_by("-calc_no")
        .first()
    )
    seq = int(last.calc_no[-3:]) + 1 if last else 1
    return f"{prefix}{seq:03d}"


def create_calculation(*, part, rule, user, data, status="confirmed", remark=""):
    """按快照参数创建核价单及分项明细。data 为 compute_cost 的入参。"""
    payload = dict(data)
    price_date = payload.pop("price_date", timezone.localdate())
    values = compute_cost(**payload)
    calc = CostCalculation.objects.create(
        calc_no=next_calc_no(),
        part=part,
        rule=rule,
        status=status,
        created_by=user,
        material_price=values["material_price"],
        material_price_date=price_date,
        net_weight=values["net_weight"],
        loss_rate=values["loss_rate"],
        material_input_weight=values["material_input_weight"],
        material_cost=values["material_cost"],
        processing_fee=values["processing_fee"],
        outsourcing_fee=values["outsourcing_fee"],
        packaging_fee=values["packaging_fee"],
        overhead_fee=values["overhead_fee"],
        scrap_weight=values["scrap_weight"],
        scrap_price=values["scrap_price"],
        scrap_recovery=values["scrap_recovery"],
        unit_cost=values["unit_cost"],
        markup_rate=values["markup_rate"],
        reference_price=values["reference_price"],
        deviation_low=rule.deviation_low,
        deviation_high=rule.deviation_high,
        rule_version=rule.version,
        remark=remark,
    )

    rows = [
        ("material", "材料成本", values["material_input_weight"], "kg", values["material_price"],
         values["material_cost"],
         f"{values['net_weight']}kg ÷ (1-{values['loss_rate']}%) × {values['material_price']}元/kg", 10),
        ("processing", "工序加工费", 1, "件", values["processing_fee"], values["processing_fee"],
         "按工序加工费规则计入", 20),
        ("outsourcing", "外协及表面处理费", 1, "件", values["outsourcing_fee"], values["outsourcing_fee"],
         "外协加工 / 表面处理", 30),
        ("packaging", "包装物流费", 1, "件", values["packaging_fee"], values["packaging_fee"],
         "包装材料与物流分摊", 40),
        ("overhead", "分摊制造费用", 1, "件", values["overhead_fee"], values["overhead_fee"],
         "按制造费用分摊规则", 50),
        ("scrap", "废料回收价值（减项）", values["scrap_weight"], "kg", values["scrap_price"],
         -values["scrap_recovery"],
         f"({values['material_input_weight']}kg - {values['net_weight']}kg) × {values['scrap_price']}元/kg", 60),
    ]
    CostCalculationDetail.objects.bulk_create(
        [
            CostCalculationDetail(
                calculation=calc,
                item_type=item_type,
                item_name=name,
                quantity=q4(quantity),
                unit=unit,
                unit_price=q4(price),
                amount=q2(amount),
                formula_text=formula,
                sort_order=order,
            )
            for item_type, name, quantity, unit, price, amount, formula, order in rows
        ]
    )
    return calc


def latest_calculation(part, confirmed_only=True):
    qs = part.calculations.all()
    if confirmed_only:
        qs = qs.filter(status="confirmed")
    return qs.order_by("-created_at", "-id").first()


def quote_metrics(quote, calc):
    """计算报价相对核价参考价的偏差金额、偏差率与预警级别。"""
    if not calc or not calc.reference_price:
        return {"deviation": None, "rate": None, "level": "unknown", "label": "缺参考价"}
    deviation = q2(quote.normalized_price - calc.reference_price)
    rate = q2(deviation / calc.reference_price * 100)
    if rate > calc.deviation_high:
        level, label = "high", "偏高"
    elif rate < calc.deviation_low:
        level, label = "low", "偏低"
    else:
        level, label = "normal", "正常"
    return {"deviation": deviation, "rate": rate, "level": level, "label": label}


def quotes_for_part(part):
    """返回零件全部报价的统一口径分析结果，按偏差率排序。"""
    calc = latest_calculation(part)
    rows = []
    for quote in part.quotes.select_related("supplier").order_by("normalized_price"):
        metric = quote_metrics(quote, calc)
        rows.append({"quote": quote, "metric": metric, "calc": calc})
    ranked = sorted(
        rows,
        key=lambda row: row["metric"]["rate"] if row["metric"]["rate"] is not None else Decimal("999"),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return calc, ranked


def dashboard_stats():
    from .models import Part, Supplier

    calcs = CostCalculation.objects.filter(status="confirmed")
    quotes = SupplierQuote.objects.select_related("part", "supplier")
    rates = []
    alerts = []
    for quote in quotes:
        calc = latest_calculation(quote.part)
        metric = quote_metrics(quote, calc)
        if metric["rate"] is not None:
            rates.append(metric["rate"])
            if metric["level"] in ("high", "low"):
                alerts.append({"quote": quote, "metric": metric, "calc": calc})
    alerts.sort(key=lambda item: abs(item["metric"]["rate"]), reverse=True)
    avg_abs_rate = q2(sum(abs(rate) for rate in rates) / len(rates)) if rates else Decimal("0")
    return {
        "calc_count": calcs.count(),
        "quote_count": quotes.count(),
        "part_count": Part.objects.filter(status=True).count(),
        "supplier_count": Supplier.objects.filter(status="合格").count(),
        "avg_deviation": avg_abs_rate,
        "alerts": alerts,
        "alert_count": len(alerts),
    }


def supplier_performance():
    """供应商维度：报价次数与平均绝对偏差，用于分析页。"""
    rows = {}
    for quote in SupplierQuote.objects.select_related("supplier", "part"):
        calc = latest_calculation(quote.part)
        metric = quote_metrics(quote, calc)
        if metric["rate"] is None:
            continue
        item = rows.setdefault(
            quote.supplier_id,
            {"supplier": quote.supplier, "count": 0, "total_abs": Decimal("0"), "high": 0},
        )
        item["count"] += 1
        item["total_abs"] += abs(metric["rate"])
        if metric["level"] != "normal":
            item["high"] += 1
    result = []
    for item in rows.values():
        item["avg_abs"] = q2(item["total_abs"] / item["count"])
        result.append(item)
    result.sort(key=lambda item: item["avg_abs"])
    return result
