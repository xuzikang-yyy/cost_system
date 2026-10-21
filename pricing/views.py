import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .exports import build_calc_list_workbook, build_calc_workbook
from .forms import (
    CalculationForm,
    CostRuleForm,
    MaterialForm,
    MaterialPriceForm,
    PartForm,
    SupplierForm,
    SupplierQuoteForm,
    SystemSettingForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import (
    CostCalculation,
    CostRule,
    LoginAudit,
    Material,
    MaterialPrice,
    Part,
    Supplier,
    SupplierQuote,
    SystemSetting,
)
from .services import (
    active_rule,
    create_calculation,
    dashboard_stats,
    latest_calculation,
    next_calc_no,
    price_on,
    q2,
    quote_metrics,
    quotes_for_part,
    supplier_performance,
)


class StyledAuthForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "请输入账号", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "请输入密码"}
        )


def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "该功能仅管理员可操作。")
            return redirect("pricing:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper


def login_view(request):
    if request.user.is_authenticated:
        return redirect("pricing:dashboard")
    form = StyledAuthForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f"欢迎回来，{form.get_user().get_full_name() or form.get_user().username}。")
        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("pricing:dashboard")
    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("pricing:login")


def month_ends(count=8):
    today = timezone.localdate()
    year, month = today.year, today.month
    points = []
    for _ in range(count):
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        end = date(next_year, next_month, 1) - timezone.timedelta(days=1)
        points.append((f"{year}-{month:02d}", end))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return list(reversed(points))


def material_trend(months=8):
    materials = list(Material.objects.filter(status=True)[:4])
    labels = [label for label, _ in month_ends(months)]
    series = []
    for material in materials:
        values = []
        for _, end in month_ends(months):
            price = price_on(material, end)
            values.append(float(price.price) if price else None)
        series.append({"name": material.name, "data": values})
    return {
        "labels": labels,
        "series": series,
        "materials": [
            {"name": material.name, "unit": material.unit, "type": material.material_type}
            for material in materials
        ],
    }


@login_required
def dashboard(request):
    stats = dashboard_stats()
    calcs = CostCalculation.objects.filter(status="confirmed").select_related("part", "created_by")
    recent = list(calcs[:6])
    today = timezone.localdate()
    month_count = calcs.filter(created_at__year=today.year, created_at__month=today.month).count()

    latest_by_part = {}
    for calc in calcs:
        latest_by_part.setdefault(calc.part_id, calc)
    cost_items = [
        ("材料成本", Decimal("0")),
        ("工序加工费", Decimal("0")),
        ("外协及表面处理", Decimal("0")),
        ("包装物流", Decimal("0")),
        ("分摊制造费用", Decimal("0")),
    ]
    sample = list(latest_by_part.values())[:6]
    if sample:
        cost_items = []
        for label, _ in [
            ("材料成本", 0), ("工序加工费", 0), ("外协及表面处理", 0),
            ("包装物流", 0), ("分摊制造费用", 0),
        ]:
            total = Decimal("0")
            for calc in sample:
                total += dict(calc.cost_items)[label]
            cost_items.append((label, q2(total / len(sample))))

    chart = {
        "trend": material_trend(8),
        "cost": {
            "labels": [label for label, _ in cost_items],
            "values": [float(value) for _, value in cost_items],
        },
    }
    return render(
        request,
        "dashboard.html",
        {
            "stats": stats,
            "recent": recent,
            "month_count": month_count,
            "chart": chart,
            "sample_count": len(sample),
            "today": today,
        },
    )


@login_required
def material_list(request):
    query = request.GET.get("q", "").strip()
    materials = Material.objects.all()
    if query:
        materials = materials.filter(
            Q(code__icontains=query) | Q(name__icontains=query) | Q(specification__icontains=query)
        )
    rows = []
    for material in materials:
        latest = material.latest_price()
        previous = (
            material.prices.exclude(pk=latest.pk).order_by("-effective_date", "-id").first()
            if latest
            else None
        )
        change = None
        if latest and previous and previous.price:
            change = q2((latest.price - previous.price) / previous.price * 100)
        rows.append({"material": material, "latest": latest, "change": change})
    return render(request, "materials/list.html", {"rows": rows, "query": query})


@admin_required
def material_create(request):
    form = MaterialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        material = form.save()
        messages.success(request, f"原材料 {material.name} 已创建，请补充价格记录。")
        return redirect("pricing:material_detail", pk=material.pk)
    return render(request, "materials/form.html", {"form": form, "title": "新增原材料"})


@admin_required
def material_edit(request, pk):
    material = get_object_or_404(Material, pk=pk)
    form = MaterialForm(request.POST or None, instance=material)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "原材料信息已更新。")
        return redirect("pricing:material_detail", pk=material.pk)
    return render(
        request,
        "materials/form.html",
        {"form": form, "title": f"编辑原材料 · {material.name}", "material": material},
    )


@login_required
def material_detail(request, pk):
    material = get_object_or_404(Material, pk=pk)
    prices = material.prices.order_by("-effective_date")
    form = MaterialPriceForm(initial={"material": material, "effective_date": timezone.localdate()})
    if request.method == "POST":
        if not request.user.is_superuser:
            return HttpResponseForbidden("仅管理员可维护材料价格")
        form = MaterialPriceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "材料价格已记录。")
            return redirect("pricing:material_detail", pk=pk)
    latest = prices.first()
    price_list = list(prices)
    price_rows = []
    for price in price_list:
        older = (
            MaterialPrice.objects.filter(
                material=material, effective_date__lt=price.effective_date
            )
            .order_by("-effective_date")
            .first()
        )
        change = None
        if older and older.price:
            change = q2((price.price - older.price) / older.price * 100)
        price_rows.append({"price": price, "change": change})
    chart = {
        "labels": [price.effective_date.strftime("%Y-%m-%d") for price in reversed(price_list)],
        "values": [float(price.price) for price in reversed(price_list)],
    }
    parts = material.parts.all()
    return render(
        request,
        "materials/detail.html",
        {
            "material": material,
            "prices": prices,
            "price_rows": price_rows,
            "latest": latest,
            "form": form,
            "chart": chart,
            "parts": parts,
        },
    )


@login_required
def part_list(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    parts = Part.objects.select_related("material").prefetch_related("quotes", "calculations")
    if query:
        parts = parts.filter(
            Q(code__icontains=query) | Q(name__icontains=query) | Q(specification__icontains=query)
        )
    if category:
        parts = parts.filter(category=category)
    rows = []
    for part in parts:
        calc = latest_calculation(part)
        rows.append(
            {
                "part": part,
                "calc": calc,
                "quote_count": part.quotes.count(),
                "quote_min": part.quotes.order_by("normalized_price").first(),
            }
        )
    return render(
        request,
        "parts/list.html",
        {"rows": rows, "query": query, "category": category, "categories": Part.CATEGORY_CHOICES},
    )


@admin_required
def part_create(request):
    form = PartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        part = form.save()
        messages.success(request, f"零件 {part.name} 已创建。")
        return redirect("pricing:part_detail", pk=part.pk)
    return render(request, "parts/form.html", {"form": form, "title": "新增零件"})


@admin_required
def part_edit(request, pk):
    part = get_object_or_404(Part, pk=pk)
    form = PartForm(request.POST or None, instance=part)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "零件信息已更新。")
        return redirect("pricing:part_detail", pk=part.pk)
    return render(
        request, "parts/form.html", {"form": form, "title": f"编辑零件 · {part.name}", "part": part}
    )


@login_required
def part_detail(request, pk):
    part = get_object_or_404(Part.objects.select_related("material"), pk=pk)
    calc, rows = quotes_for_part(part)
    history = part.calculations.select_related("created_by").order_by("-created_at")[:8]
    rates = [row["metric"]["rate"] for row in rows if row["metric"]["rate"] is not None]
    avg_rate = q2(sum(rates) / len(rates)) if rates else None
    abnormal = [row for row in rows if row["metric"]["level"] != "normal"]
    chart = {
        "suppliers": [row["quote"].supplier.name for row in rows],
        "quotes": [float(row["quote"].normalized_price) for row in rows],
        "rates": [float(row["metric"]["rate"]) if row["metric"]["rate"] is not None else 0 for row in rows],
        "levels": [row["metric"]["level"] for row in rows],
        "reference": float(calc.reference_price) if calc else 0,
        "low": float(calc.reference_price * (1 + calc.deviation_low / 100)) if calc else 0,
        "high": float(calc.reference_price * (1 + calc.deviation_high / 100)) if calc else 0,
        "rate_range": [float(calc.deviation_low) if calc else -8, float(calc.deviation_high) if calc else 8],
    }
    return render(
        request,
        "parts/detail.html",
        {
            "part": part,
            "calc": calc,
            "rows": rows,
            "history": history,
            "avg_rate": avg_rate,
            "abnormal": abnormal,
            "chart": chart,
        },
    )


@login_required
def rule_list(request):
    rules = CostRule.objects.all()
    return render(request, "rules/list.html", {"rules": rules})


@admin_required
def rule_create(request):
    form = CostRuleForm(request.POST or None, initial={"effective_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "成本规则已创建。")
        return redirect("pricing:rule_list")
    return render(request, "rules/form.html", {"form": form, "title": "新增成本规则"})


@admin_required
def rule_edit(request, pk):
    rule = get_object_or_404(CostRule, pk=pk)
    form = CostRuleForm(request.POST or None, instance=rule)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "成本规则已更新。")
        return redirect("pricing:rule_list")
    return render(
        request, "rules/form.html", {"form": form, "title": f"编辑规则 · {rule.name}", "rule": rule}
    )


@login_required
def supplier_list(request):
    query = request.GET.get("q", "").strip()
    suppliers = Supplier.objects.all()
    if query:
        suppliers = suppliers.filter(
            Q(code__icontains=query) | Q(name__icontains=query) | Q(contact__icontains=query)
        )
    perf = {item["supplier"].id: item for item in supplier_performance()}
    rows = []
    for supplier in suppliers:
        rows.append(
            {
                "supplier": supplier,
                "quote_count": supplier.quotes.count(),
                "perf": perf.get(supplier.id),
            }
        )
    return render(request, "suppliers/list.html", {"rows": rows, "query": query})


@admin_required
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "供应商已创建。")
        return redirect("pricing:supplier_list")
    return render(request, "suppliers/form.html", {"form": form, "title": "新增供应商"})


@admin_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "供应商信息已更新。")
        return redirect("pricing:supplier_list")
    return render(
        request,
        "suppliers/form.html",
        {"form": form, "title": f"编辑供应商 · {supplier.name}", "supplier": supplier},
    )


def _quote_rows(quotes):
    calc_cache = {}
    rows = []
    for quote in quotes:
        if quote.part_id not in calc_cache:
            calc_cache[quote.part_id] = latest_calculation(quote.part)
        calc = calc_cache[quote.part_id]
        rows.append(
            {"quote": quote, "calc": calc, "metric": quote_metrics(quote, calc)}
        )
    return rows


@login_required
def quote_list(request):
    query = request.GET.get("q", "").strip()
    supplier_id = request.GET.get("supplier", "")
    level = request.GET.get("level", "")
    quotes = SupplierQuote.objects.select_related("supplier", "part")
    if query:
        quotes = quotes.filter(
            Q(part__code__icontains=query)
            | Q(part__name__icontains=query)
            | Q(supplier__name__icontains=query)
        )
    if supplier_id:
        quotes = quotes.filter(supplier_id=supplier_id)
    rows = _quote_rows(quotes.order_by("-quote_date", "-id"))
    if level:
        rows = [row for row in rows if row["metric"]["level"] == level]
    page = Paginator(rows, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "quotes/list.html",
        {
            "page": page,
            "rows": page.object_list,
            "query": query,
            "supplier_id": supplier_id,
            "level": level,
            "suppliers": Supplier.objects.filter(status__in=["合格", "观察"]),
            "total": len(rows),
        },
    )


@login_required
def quote_create(request):
    initial = {}
    if request.GET.get("part"):
        initial["part"] = request.GET.get("part")
    if request.GET.get("supplier"):
        initial["supplier"] = request.GET.get("supplier")
    initial["quote_date"] = timezone.localdate()
    form = SupplierQuoteForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        quote = form.save()
        calc = latest_calculation(quote.part)
        metric = quote_metrics(quote, calc)
        if metric["rate"] is None:
            messages.warning(request, "报价已保存，但该零件尚无已确认核价单，暂时无法计算偏差。")
        else:
            messages.success(
                request,
                f"报价已保存：统一口径 {quote.normalized_price:.2f} 元/件（不含税），"
                f"较参考报价偏差 {metric['rate']:+.2f}%（{metric['label']}）。",
            )
        return redirect("pricing:part_detail", pk=quote.part_id)
    return render(
        request,
        "quotes/form.html",
        {"form": form, "title": "录入供应商报价", "quote": None, "parts_info": _parts_info()},
    )


def _parts_info():
    info = {}
    for part in Part.objects.filter(status=True):
        calc = latest_calculation(part)
        info[str(part.pk)] = {
            "name": part.name,
            "net_weight": float(part.net_weight),
            "reference": float(calc.reference_price) if calc else 0,
            "low": float(calc.deviation_low) if calc else -8,
            "high": float(calc.deviation_high) if calc else 8,
        }
    return info


@login_required
def quote_edit(request, pk):
    quote = get_object_or_404(SupplierQuote, pk=pk)
    form = SupplierQuoteForm(request.POST or None, instance=quote)
    if request.method == "POST" and form.is_valid():
        quote = form.save()
        messages.success(request, "报价已更新，偏差结果同步刷新。")
        return redirect("pricing:part_detail", pk=quote.part_id)
    return render(
        request,
        "quotes/form.html",
        {
            "form": form,
            "title": f"编辑报价 · {quote.supplier.name}",
            "quote": quote,
            "parts_info": _parts_info(),
        },
    )


@login_required
def quote_delete(request, pk):
    quote = get_object_or_404(SupplierQuote, pk=pk)
    if not request.user.is_superuser:
        return HttpResponseForbidden("仅管理员可删除报价")
    if request.method == "POST":
        part_id = quote.part_id
        quote.delete()
        messages.success(request, "报价记录已删除。")
        return redirect("pricing:part_detail", pk=part_id)
    return redirect("pricing:quote_list")


@login_required
def calc_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    calcs = CostCalculation.objects.select_related("part", "created_by", "part__material")
    if query:
        calcs = calcs.filter(
            Q(calc_no__icontains=query)
            | Q(part__code__icontains=query)
            | Q(part__name__icontains=query)
        )
    if status:
        calcs = calcs.filter(status=status)
    page = Paginator(calcs, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "calculations/list.html",
        {"page": page, "calcs": page.object_list, "query": query, "status": status},
    )


@login_required
def calc_create(request):
    parts = Part.objects.filter(status=True).select_related("material")
    initial = {
        "price_date": timezone.localdate(),
        "status": "confirmed",
        "markup_rate": SystemSetting.load().default_markup_rate,
    }
    if request.GET.get("part"):
        part = parts.filter(pk=request.GET.get("part")).first()
        if part:
            initial["part"] = part
            initial["net_weight"] = part.net_weight
            price = price_on(part.material)
            if price:
                initial["material_price"] = price.price
                initial["price_date"] = price.effective_date
            rule = active_rule(part)
            if rule:
                initial.update(
                    {
                        "loss_rate": rule.loss_rate,
                        "processing_fee": rule.processing_fee,
                        "outsourcing_fee": rule.outsourcing_fee,
                        "packaging_fee": rule.packaging_fee,
                        "overhead_fee": rule.overhead_fee,
                        "scrap_price": rule.scrap_price,
                        "markup_rate": rule.markup_rate,
                    }
                )
    if request.method == "POST":
        form = CalculationForm(request.POST)
        if form.is_valid():
            part = form.cleaned_data["part"]
            rule = active_rule(part, form.cleaned_data["price_date"])
            if not rule:
                form.add_error(None, "该零件类别没有生效中的成本规则，请先在基础数据中维护。")
            else:
                data = {
                    "net_weight": form.cleaned_data["net_weight"],
                    "material_price": form.cleaned_data["material_price"],
                    "loss_rate": form.cleaned_data["loss_rate"],
                    "processing_fee": form.cleaned_data["processing_fee"],
                    "outsourcing_fee": form.cleaned_data["outsourcing_fee"],
                    "packaging_fee": form.cleaned_data["packaging_fee"],
                    "overhead_fee": form.cleaned_data["overhead_fee"],
                    "scrap_price": form.cleaned_data["scrap_price"],
                    "markup_rate": form.cleaned_data["markup_rate"],
                    "price_date": form.cleaned_data["price_date"],
                }
                calc = create_calculation(
                    part=part,
                    rule=rule,
                    user=request.user,
                    data=data,
                    status=form.cleaned_data["status"],
                    remark=form.cleaned_data["remark"],
                )
                messages.success(request, f"核价单 {calc.calc_no} 已生成。")
                return redirect("pricing:calc_detail", pk=calc.pk)
    else:
        form = CalculationForm(initial=initial)

    config = {}
    for part in parts:
        price = price_on(part.material)
        rule = active_rule(part)
        config[str(part.pk)] = {
            "code": part.code,
            "name": part.name,
            "category": part.category,
            "material": part.material.name,
            "net_weight": float(part.net_weight),
            "price": float(price.price) if price else 0,
            "price_date": price.effective_date.isoformat() if price else "",
            "rule": {
                "loss_rate": float(rule.loss_rate) if rule else 3,
                "processing_fee": float(rule.processing_fee) if rule else 0,
                "outsourcing_fee": float(rule.outsourcing_fee) if rule else 0,
                "packaging_fee": float(rule.packaging_fee) if rule else 0,
                "overhead_fee": float(rule.overhead_fee) if rule else 0,
                "scrap_price": float(rule.scrap_price) if rule else 0,
                "markup_rate": float(rule.markup_rate) if rule else 8,
                "deviation_low": float(rule.deviation_low) if rule else -8,
                "deviation_high": float(rule.deviation_high) if rule else 8,
            }
            if rule
            else None,
        }
    return render(
        request,
        "calculations/form.html",
        {
            "form": form,
            "parts_config": config,
            "next_no": next_calc_no(),
        },
    )


@login_required
def calc_detail(request, pk):
    calc = get_object_or_404(
        CostCalculation.objects.select_related("part", "part__material", "created_by", "rule"), pk=pk
    )
    part = calc.part
    _, rows = quotes_for_part(part)
    for row in rows:
        row["current_metric"] = quote_metrics(row["quote"], calc)
    rows.sort(
        key=lambda row: row["current_metric"]["rate"]
        if row["current_metric"]["rate"] is not None
        else Decimal("999")
    )
    for index, row in enumerate(rows, start=1):
        row["current_rank"] = index
    history = (
        part.calculations.select_related("created_by")
        .exclude(pk=calc.pk)
        .order_by("-created_at")[:5]
    )
    chart = {
        "labels": [label for label, _ in calc.cost_items],
        "values": [float(value) for _, value in calc.cost_items],
        "scrap": float(calc.scrap_recovery),
        "reference": float(calc.reference_price),
        "unit_cost": float(calc.unit_cost),
    }
    return render(
        request,
        "calculations/detail.html",
        {
            "calc": calc,
            "part": part,
            "rows": rows,
            "history": history,
            "chart": chart,
            "tax_reference": q2(calc.reference_price * Decimal("1.13")),
        },
    )


@login_required
@require_POST
def calc_confirm(request, pk):
    calc = get_object_or_404(CostCalculation, pk=pk)
    calc.status = "confirmed"
    calc.save(update_fields=["status"])
    messages.success(request, f"核价单 {calc.calc_no} 已确认，可作为报价对比基准。")
    return redirect("pricing:calc_detail", pk=calc.pk)


@login_required
def calc_export(request, pk):
    calc = get_object_or_404(
        CostCalculation.objects.select_related("part", "created_by", "part__material"), pk=pk
    )
    return build_calc_workbook(calc)


@login_required
def calc_export_all(request):
    calcs = CostCalculation.objects.select_related("part", "created_by").order_by("-created_at")
    return build_calc_list_workbook(calcs)


@login_required
def analysis(request):
    category = request.GET.get("category", "")
    parts = Part.objects.filter(status=True).select_related("material")
    if category:
        parts = parts.filter(category=category)

    comparison = []
    for part in parts:
        calc, rows = quotes_for_part(part)
        if not rows:
            continue
        rates = [row["metric"]["rate"] for row in rows if row["metric"]["rate"] is not None]
        comparison.append(
            {
                "part": part,
                "calc": calc,
                "quote_count": len(rows),
                "avg_rate": q2(sum(rates) / len(rates)) if rates else None,
                "min_quote": rows[0]["quote"] if rows else None,
                "max_rate": max(rates) if rates else None,
                "min_rate": min(rates) if rates else None,
            }
        )
    comparison.sort(key=lambda item: abs(item["avg_rate"] or 0), reverse=True)

    perf = supplier_performance()
    trend = material_trend(12)

    buckets = [
        ("≤ -10%", -999, -10),
        ("-10% ~ -5%", -10, -5),
        ("-5% ~ 0", -5, 0),
        ("0 ~ 5%", 0, 5),
        ("5% ~ 10%", 5, 10),
        ("> 10%", 10, 999),
    ]
    counts = [0] * len(buckets)
    all_rows = []
    for part in Part.objects.filter(status=True):
        calc, rows = quotes_for_part(part)
        all_rows.extend(rows)
    all_rates = []
    abnormal_count = 0
    for row in all_rows:
        rate = row["metric"]["rate"]
        if rate is None:
            continue
        all_rates.append(rate)
        if row["metric"]["level"] in ("high", "low"):
            abnormal_count += 1
        for index, (_, low, high) in enumerate(buckets):
            if low < float(rate) <= high:
                counts[index] += 1
                break

    avg_abs = q2(sum(abs(rate) for rate in all_rates) / len(all_rates)) if all_rates else Decimal("0")
    abnormal_pct = (
        q2(Decimal(abnormal_count) / Decimal(len(all_rates)) * 100) if all_rates else Decimal("0")
    )

    latest_by_part = {}
    calcs = CostCalculation.objects.filter(status="confirmed").select_related("part")
    for calc in calcs:
        latest_by_part.setdefault(calc.part_id, calc)
    cost_compare = [
        {
            "name": calc.part.name,
            "material": float(calc.material_cost),
            "processing": float(calc.processing_fee + calc.outsourcing_fee),
            "other": float(calc.packaging_fee + calc.overhead_fee - calc.scrap_recovery),
        }
        for calc in list(latest_by_part.values())[:8]
    ]

    first_calc = latest_calculation(parts[0]) if parts else None
    chart = {
        "trend": trend,
        "hist": {"labels": [bucket[0] for bucket in buckets], "values": counts},
        "suppliers": {
            "labels": [item["supplier"].name for item in perf],
            "values": [float(item["avg_abs"]) for item in perf],
        },
        "cost": cost_compare,
        "rate_range": [
            float(first_calc.deviation_low) if first_calc else -8,
            float(first_calc.deviation_high) if first_calc else 8,
        ],
    }
    return render(
        request,
        "analysis/index.html",
        {
            "comparison": comparison,
            "perf": perf,
            "chart": chart,
            "categories": Part.CATEGORY_CHOICES,
            "category": category,
            "quote_total": len(all_rows),
            "avg_abs": avg_abs,
            "abnormal_count": abnormal_count,
            "abnormal_pct": abnormal_pct,
            "supplier_count": Supplier.objects.filter(status="合格").count(),
            "part_count": len(comparison),
        },
    )


@admin_required
def system(request):
    setting = SystemSetting.load()
    form = SystemSettingForm(request.POST or None, instance=setting)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "系统参数已保存。")
        return redirect("pricing:system")
    users = User.objects.order_by("-is_superuser", "username")
    return render(
        request,
        "system/index.html",
        {"form": form, "settings": setting, "users": users},
    )


@admin_required
def audit_log(request):
    query = request.GET.get("q", "").strip()
    event = request.GET.get("event", "")
    rows = LoginAudit.objects.select_related("user")
    if query:
        rows = rows.filter(Q(username__icontains=query) | Q(ip__icontains=query))
    if event:
        rows = rows.filter(event=event)
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "system/audit_log.html",
        {"page": page, "rows": page.object_list, "query": query, "event": event},
    )


@admin_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
            first_name=form.cleaned_data["display_name"],
        )
        is_admin = form.cleaned_data["role"] == "admin"
        user.is_superuser = is_admin
        user.is_staff = is_admin
        user.save()
        messages.success(request, f"账号 {user.username} 已创建。")
        return redirect("pricing:system")
    return render(request, "system/user_form.html", {"form": form, "title": "新增系统用户"})


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    initial = {
        "display_name": user.first_name,
        "role": "admin" if user.is_superuser else "buyer",
        "is_active": user.is_active,
    }
    form = UserUpdateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if user == request.user and form.cleaned_data["role"] != "admin":
            form.add_error("role", "不能降低当前登录账号自身的权限。")
        elif user == request.user and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "不能停用当前登录账号。")
        else:
            user.first_name = form.cleaned_data["display_name"]
            is_admin = form.cleaned_data["role"] == "admin"
            user.is_superuser = is_admin
            user.is_staff = is_admin
            user.is_active = form.cleaned_data["is_active"]
            user.save()
            messages.success(request, "用户信息已更新。")
            return redirect("pricing:system")
    return render(
        request,
        "system/user_form.html",
        {"form": form, "title": f"编辑用户 · {user.username}", "edit_user": user},
    )
