"""采购成本核价系统数据模型。

对应论文中的 8 张核心业务表：
Material / MaterialPrice / Part / CostRule / Supplier /
SupplierQuote / CostCalculation / CostCalculationDetail
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Material(models.Model):
    """原材料基础信息（铜、铝、塑料等），价格单独存放于 MaterialPrice。"""

    TYPE_CHOICES = [
        ("铜", "铜"),
        ("铝", "铝"),
        ("塑料", "塑料"),
        ("钢", "钢"),
        ("其他", "其他"),
    ]
    UNIT_CHOICES = [("千克", "千克"), ("件", "件"), ("米", "米")]

    code = models.CharField("材料编号", max_length=30, unique=True)
    name = models.CharField("材料名称", max_length=60)
    material_type = models.CharField("材质", max_length=10, choices=TYPE_CHOICES, default="铜")
    unit = models.CharField("计价单位", max_length=10, choices=UNIT_CHOICES, default="千克")
    specification = models.CharField("常用规格", max_length=120, blank=True)
    status = models.BooleanField("启用", default=True)
    remark = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "原材料"
        verbose_name_plural = "原材料"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    def latest_price(self, on_date=None):
        qs = self.prices.all()
        if on_date:
            qs = qs.filter(effective_date__lte=on_date)
        return qs.order_by("-effective_date", "-id").first()


class MaterialPrice(models.Model):
    """材料参考价格，按生效日期保留历史，不在材料主表上覆盖。"""

    SOURCE_CHOICES = [
        ("长江有色", "长江有色"),
        ("上海有色", "上海有色"),
        ("供应商报价", "供应商报价"),
        ("历史采购", "历史采购"),
        ("手工录入", "手工录入"),
    ]

    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name="prices", verbose_name="原材料"
    )
    price = models.DecimalField("参考单价(元)", max_digits=12, decimal_places=4)
    effective_date = models.DateField("生效日期", default=timezone.localdate)
    source = models.CharField("价格来源", max_length=20, choices=SOURCE_CHOICES, default="手工录入")
    created_at = models.DateTimeField("录入时间", auto_now_add=True)

    class Meta:
        verbose_name = "原材料价格"
        verbose_name_plural = "原材料价格"
        ordering = ["-effective_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["material", "effective_date"], name="uniq_material_price_date"
            )
        ]

    def __str__(self):
        return f"{self.material.name} {self.price}元 @{self.effective_date}"


class Part(models.Model):
    """待核价零件。"""

    CATEGORY_CHOICES = [
        ("铜件", "铜件"),
        ("铝件", "铝件"),
        ("塑料件", "塑料件"),
        ("其他", "其他"),
    ]

    code = models.CharField("零件编号", max_length=30, unique=True)
    name = models.CharField("零件名称", max_length=80)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="parts", verbose_name="原材料"
    )
    category = models.CharField("零件类别", max_length=10, choices=CATEGORY_CHOICES, default="铜件")
    specification = models.CharField("规格", max_length=120, blank=True)
    net_weight = models.DecimalField(
        "成品净重(kg)", max_digits=10, decimal_places=4, default=Decimal("0.1000")
    )
    drawing_no = models.CharField("图号", max_length=60, blank=True)
    status = models.BooleanField("启用", default=True)
    remark = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "零件信息"
        verbose_name_plural = "零件信息"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class CostRule(models.Model):
    """成本规则：损耗、加工费及其他费用参数，可按零件类别配置版本。"""

    CATEGORY_CHOICES = Part.CATEGORY_CHOICES

    name = models.CharField("规则名称", max_length=80)
    category = models.CharField("适用零件类别", max_length=10, choices=CATEGORY_CHOICES)
    loss_rate = models.DecimalField(
        "损耗率(%)", max_digits=6, decimal_places=2, default=Decimal("3.00")
    )
    processing_fee = models.DecimalField(
        "工序加工费(元/件)", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    outsourcing_fee = models.DecimalField(
        "外协及表面处理费(元/件)", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    packaging_fee = models.DecimalField(
        "包装物流费(元/件)", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    overhead_fee = models.DecimalField(
        "分摊制造费用(元/件)", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    scrap_price = models.DecimalField(
        "废料回收单价(元/kg)", max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    markup_rate = models.DecimalField(
        "合理加成率(%)", max_digits=6, decimal_places=2, default=Decimal("8.00")
    )
    deviation_low = models.DecimalField(
        "偏差下限(%)", max_digits=6, decimal_places=2, default=Decimal("-8.00")
    )
    deviation_high = models.DecimalField(
        "偏差上限(%)", max_digits=6, decimal_places=2, default=Decimal("8.00")
    )
    version = models.CharField("规则版本", max_length=20, default="V1.0")
    effective_date = models.DateField("生效日期", default=timezone.localdate)
    is_active = models.BooleanField("启用", default=True)
    remark = models.CharField("说明", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "成本规则"
        verbose_name_plural = "成本规则"
        ordering = ["category", "-effective_date", "-id"]

    def __str__(self):
        return f"{self.name}（{self.category} {self.version}）"


class Supplier(models.Model):
    """供应商基础资料。"""

    CATEGORY_CHOICES = [
        ("铜件", "铜件"),
        ("铝件", "铝件"),
        ("塑料件", "塑料件"),
        ("综合", "综合"),
    ]
    STATUS_CHOICES = [("合格", "合格"), ("观察", "观察"), ("停用", "停用")]

    code = models.CharField("供应商编号", max_length=30, unique=True)
    name = models.CharField("供应商名称", max_length=100)
    category = models.CharField("供应类别", max_length=10, choices=CATEGORY_CHOICES, default="综合")
    contact = models.CharField("联系人", max_length=40, blank=True)
    phone = models.CharField("联系电话", max_length=30, blank=True)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="合格")
    remark = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "供应商"
        verbose_name_plural = "供应商"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class SupplierQuote(models.Model):
    """供应商针对具体零件的报价，保存原始口径并计算统一口径价格。"""

    PRICE_UNIT_CHOICES = [("件", "元/件"), ("千克", "元/千克")]
    CURRENCY_CHOICES = [("CNY", "人民币"), ("USD", "美元")]

    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="quotes", verbose_name="供应商"
    )
    part = models.ForeignKey(
        Part, on_delete=models.CASCADE, related_name="quotes", verbose_name="零件"
    )
    unit_price = models.DecimalField("报价", max_digits=12, decimal_places=2)
    price_unit = models.CharField("报价单位", max_length=10, choices=PRICE_UNIT_CHOICES, default="件")
    quote_date = models.DateField("报价日期", default=timezone.localdate)
    tax_included = models.BooleanField("含税", default=True)
    tax_rate = models.DecimalField(
        "税率(%)", max_digits=5, decimal_places=2, default=Decimal("13.00")
    )
    currency = models.CharField("币种", max_length=5, choices=CURRENCY_CHOICES, default="CNY")
    exchange_rate = models.DecimalField("汇率", max_digits=8, decimal_places=4, default=Decimal("1.0000"))
    lead_time_days = models.PositiveIntegerField("交期(天)", default=15)
    normalized_price = models.DecimalField(
        "统一口径单价(元/件,不含税)", max_digits=12, decimal_places=4, default=Decimal("0.0000")
    )
    remark = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("录入时间", auto_now_add=True)

    class Meta:
        verbose_name = "供应商报价"
        verbose_name_plural = "供应商报价"
        ordering = ["quote_date", "normalized_price"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "part", "quote_date"], name="uniq_quote_supplier_part_date"
            )
        ]

    def __str__(self):
        return f"{self.supplier.name} / {self.part.name} {self.unit_price}"

    def calculate_normalized(self):
        """统一为人民币、不含税、元/件的口径，供横向比较。"""
        price = Decimal(self.unit_price or 0)
        if self.price_unit == "千克":
            price = price * (self.part.net_weight or 0)
        if self.tax_included:
            price = price / (Decimal("1") + (self.tax_rate or 0) / Decimal("100"))
        if self.currency == "USD":
            price = price * (self.exchange_rate or 1)
        return price.quantize(Decimal("0.0001"))

    def save(self, *args, **kwargs):
        self.normalized_price = self.calculate_normalized()
        super().save(*args, **kwargs)

    @property
    def tax_label(self):
        return "含税" if self.tax_included else "不含税"


class CostCalculation(models.Model):
    """核价单主表，保存计算时的全部关键参数快照，保证历史结果可追溯。"""

    STATUS_CHOICES = [("draft", "草稿"), ("confirmed", "已确认")]

    calc_no = models.CharField("核价编号", max_length=30, unique=True)
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="calculations", verbose_name="零件"
    )
    rule = models.ForeignKey(
        CostRule, on_delete=models.PROTECT, related_name="calculations", verbose_name="成本规则"
    )
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="calculations",
        verbose_name="核价人",
    )
    created_at = models.DateTimeField("核价时间", default=timezone.now)

    material_price = models.DecimalField("材料单价(元/kg)", max_digits=12, decimal_places=4)
    material_price_date = models.DateField("材料价格日期")
    net_weight = models.DecimalField("成品净重(kg)", max_digits=10, decimal_places=4)
    loss_rate = models.DecimalField("损耗率(%)", max_digits=6, decimal_places=2)
    material_input_weight = models.DecimalField(
        "材料投入量(kg)", max_digits=12, decimal_places=4, default=Decimal("0")
    )
    material_cost = models.DecimalField("材料成本(元)", max_digits=12, decimal_places=2, default=0)
    processing_fee = models.DecimalField("工序加工费(元)", max_digits=12, decimal_places=2, default=0)
    outsourcing_fee = models.DecimalField("外协及表面处理费(元)", max_digits=12, decimal_places=2, default=0)
    packaging_fee = models.DecimalField("包装物流费(元)", max_digits=12, decimal_places=2, default=0)
    overhead_fee = models.DecimalField("分摊制造费用(元)", max_digits=12, decimal_places=2, default=0)
    scrap_weight = models.DecimalField("废料重量(kg)", max_digits=10, decimal_places=4, default=0)
    scrap_price = models.DecimalField("废料回收单价(元/kg)", max_digits=10, decimal_places=2, default=0)
    scrap_recovery = models.DecimalField("废料回收价值(元)", max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField("理论单位成本(元)", max_digits=12, decimal_places=2, default=0)
    markup_rate = models.DecimalField("合理加成率(%)", max_digits=6, decimal_places=2, default=0)
    reference_price = models.DecimalField("核价参考报价(元)", max_digits=12, decimal_places=2, default=0)
    deviation_low = models.DecimalField("偏差下限(%)", max_digits=6, decimal_places=2, default=-8)
    deviation_high = models.DecimalField("偏差上限(%)", max_digits=6, decimal_places=2, default=8)
    rule_version = models.CharField("规则版本", max_length=20, default="V1.0")
    remark = models.CharField("核价说明", max_length=300, blank=True)

    class Meta:
        verbose_name = "核价单"
        verbose_name_plural = "核价单"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.calc_no} / {self.part.name}"

    @property
    def status_label(self):
        return "已确认" if self.status == "confirmed" else "草稿"

    @property
    def is_confirmed(self):
        return self.status == "confirmed"

    @property
    def cost_items(self):
        """按业务类型返回成本分项，用于结果页与图表。"""
        return [
            ("材料成本", self.material_cost),
            ("工序加工费", self.processing_fee),
            ("外协及表面处理", self.outsourcing_fee),
            ("包装物流", self.packaging_fee),
            ("分摊制造费用", self.overhead_fee),
        ]

    @property
    def total_positive_cost(self):
        return sum((amount for _, amount in self.cost_items), Decimal("0"))


class CostCalculationDetail(models.Model):
    """核价明细：保存每一项成本的计算过程，而不只是最终总价。"""

    ITEM_TYPE_CHOICES = [
        ("material", "材料成本"),
        ("processing", "工序加工费"),
        ("outsourcing", "外协及表面处理"),
        ("packaging", "包装物流"),
        ("overhead", "分摊制造费用"),
        ("scrap", "废料回收"),
    ]

    calculation = models.ForeignKey(
        CostCalculation, on_delete=models.CASCADE, related_name="details", verbose_name="核价单"
    )
    item_type = models.CharField("费用类型", max_length=20, choices=ITEM_TYPE_CHOICES)
    item_name = models.CharField("费用项目", max_length=60)
    quantity = models.DecimalField("数量", max_digits=12, decimal_places=4, default=1)
    unit = models.CharField("单位", max_length=10, default="件")
    unit_price = models.DecimalField("单价(元)", max_digits=12, decimal_places=4, default=0)
    amount = models.DecimalField("金额(元)", max_digits=12, decimal_places=2, default=0)
    formula_text = models.CharField("计算说明", max_length=200, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "核价明细"
        verbose_name_plural = "核价明细"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.item_name} {self.amount}"


class LoginAudit(models.Model):
    """登录审计：记录成功、失败与退出事件，含客户端 IP 与来源。"""

    EVENT_CHOICES = [
        ("login", "登录成功"),
        ("failed", "登录失败"),
        ("logout", "退出登录"),
    ]

    username = models.CharField("登录账号", max_length=150, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="login_audits", verbose_name="用户",
    )
    event = models.CharField("事件", max_length=10, choices=EVENT_CHOICES)
    ip = models.CharField("客户端 IP", max_length=64, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    created_at = models.DateTimeField("发生时间", auto_now_add=True)

    class Meta:
        verbose_name = "登录审计"
        verbose_name_plural = "登录审计"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.get_event_display()} {self.username} {self.ip}"


class SystemSetting(models.Model):
    """系统级参数（单例）：默认加成率、默认偏差阈值、汇率与公司信息。"""

    company_name = models.CharField("公司名称", max_length=100, default="采购成本核价中心")
    default_markup_rate = models.DecimalField(
        "默认合理加成率(%)", max_digits=6, decimal_places=2, default=Decimal("8.00")
    )
    default_deviation_low = models.DecimalField(
        "默认偏差下限(%)", max_digits=6, decimal_places=2, default=Decimal("-8.00")
    )
    default_deviation_high = models.DecimalField(
        "默认偏差上限(%)", max_digits=6, decimal_places=2, default=Decimal("8.00")
    )
    usd_rate = models.DecimalField("美元汇率", max_digits=8, decimal_places=4, default=Decimal("7.1000"))
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "系统设置"
        verbose_name_plural = "系统设置"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
