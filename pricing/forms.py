"""表单定义：统一 Bootstrap 样式与业务校验。"""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import (
    CostRule,
    Material,
    MaterialPrice,
    Part,
    Supplier,
    SupplierQuote,
    SystemSetting,
)

User = get_user_model()

BASE_CLASS = "form-control"
SELECT_CLASS = "form-select"


class BootstrapMixin:
    """为所有字段附加 Bootstrap 样式，日期与数值控件使用原生控件。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", SELECT_CLASS)
            else:
                widget.attrs.setdefault("class", BASE_CLASS)
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
            if isinstance(widget, forms.NumberInput):
                widget.attrs.setdefault("step", "0.01")
            if field.required:
                widget.attrs.setdefault("required", "required")


class MaterialForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = ["code", "name", "material_type", "unit", "specification", "status", "remark"]


class MaterialPriceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = MaterialPrice
        fields = ["material", "price", "effective_date", "source"]
        widgets = {"effective_date": forms.DateInput(attrs={"type": "date"})}

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("材料单价必须大于 0")
        return price


class PartForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Part
        fields = [
            "code", "name", "material", "category", "specification",
            "net_weight", "drawing_no", "status", "remark",
        ]
        widgets = {"net_weight": forms.NumberInput(attrs={"step": "0.0001", "min": "0.0001"})}

    def clean_net_weight(self):
        weight = self.cleaned_data["net_weight"]
        if weight <= 0:
            raise forms.ValidationError("成品净重必须大于 0")
        return weight


class CostRuleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CostRule
        fields = [
            "name", "category", "loss_rate", "processing_fee", "outsourcing_fee",
            "packaging_fee", "overhead_fee", "scrap_price", "markup_rate",
            "deviation_low", "deviation_high", "version", "effective_date",
            "is_active", "remark",
        ]
        widgets = {"effective_date": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("deviation_low"), cleaned.get("deviation_high")
        loss = cleaned.get("loss_rate")
        if low is not None and high is not None and low >= high:
            raise forms.ValidationError("偏差下限必须小于偏差上限")
        if loss is not None and (loss < 0 or loss >= 100):
            raise forms.ValidationError("损耗率必须在 0% 到 100% 之间")
        return cleaned


class SupplierForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["code", "name", "category", "contact", "phone", "status", "remark"]


class SupplierQuoteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SupplierQuote
        fields = [
            "supplier", "part", "unit_price", "price_unit", "quote_date",
            "tax_included", "tax_rate", "currency", "exchange_rate",
            "lead_time_days", "remark",
        ]
        widgets = {"quote_date": forms.DateInput(attrs={"type": "date"})}

    def clean_unit_price(self):
        price = self.cleaned_data["unit_price"]
        if price <= 0:
            raise forms.ValidationError("报价必须大于 0")
        return price

    def clean(self):
        cleaned = super().clean()
        supplier = cleaned.get("supplier")
        part = cleaned.get("part")
        quote_date = cleaned.get("quote_date")
        if supplier and part and quote_date:
            exists = SupplierQuote.objects.filter(
                supplier=supplier, part=part, quote_date=quote_date
            )
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError("该供应商在同一日期已录入过此零件报价，请修改原记录。")
        return cleaned


class CalculationForm(BootstrapMixin, forms.Form):
    """核价录入表单，所有参数在保存时形成快照。"""

    part = forms.ModelChoiceField(
        queryset=Part.objects.filter(status=True).select_related("material"),
        label="零件",
        empty_label="请选择零件",
    )
    price_date = forms.DateField(
        label="材料价格日期", widget=forms.DateInput(attrs={"type": "date"})
    )
    material_price = forms.DecimalField(
        label="材料单价(元/kg)", max_digits=12, decimal_places=4,
        widget=forms.NumberInput(attrs={"step": "0.0001"}),
    )
    net_weight = forms.DecimalField(
        label="成品净重(kg)", max_digits=10, decimal_places=4,
        widget=forms.NumberInput(attrs={"step": "0.0001"}),
    )
    loss_rate = forms.DecimalField(
        label="损耗率(%)", max_digits=6, decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )
    processing_fee = forms.DecimalField(
        label="工序加工费(元/件)", max_digits=10, decimal_places=2, initial=Decimal("0")
    )
    outsourcing_fee = forms.DecimalField(
        label="外协及表面处理费(元/件)", max_digits=10, decimal_places=2, initial=Decimal("0")
    )
    packaging_fee = forms.DecimalField(
        label="包装物流费(元/件)", max_digits=10, decimal_places=2, initial=Decimal("0")
    )
    overhead_fee = forms.DecimalField(
        label="分摊制造费用(元/件)", max_digits=10, decimal_places=2, initial=Decimal("0")
    )
    scrap_price = forms.DecimalField(
        label="废料回收单价(元/kg)", max_digits=10, decimal_places=2, initial=Decimal("0")
    )
    markup_rate = forms.DecimalField(
        label="合理加成率(%)", max_digits=6, decimal_places=2, initial=Decimal("8")
    )
    status = forms.ChoiceField(
        label="保存状态", choices=[("confirmed", "直接确认"), ("draft", "保存草稿")],
        initial="confirmed",
    )
    remark = forms.CharField(
        label="核价说明", required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "可填写询价背景、特殊工艺说明等"}),
    )

    def clean(self):
        cleaned = super().clean()
        net_weight = cleaned.get("net_weight")
        loss = cleaned.get("loss_rate")
        price = cleaned.get("material_price")
        if net_weight is not None and net_weight <= 0:
            raise forms.ValidationError("成品净重必须大于 0")
        if loss is not None and (loss < 0 or loss >= 100):
            raise forms.ValidationError("损耗率必须在 0% 到 100% 之间")
        if price is not None and price <= 0:
            raise forms.ValidationError("材料单价必须大于 0")
        markup = cleaned.get("markup_rate")
        if markup is not None and markup < 0:
            raise forms.ValidationError("合理加成率不能为负数")
        return cleaned


class UserCreateForm(BootstrapMixin, forms.Form):
    username = forms.CharField(label="登录账号", max_length=50)
    display_name = forms.CharField(label="姓名", max_length=50, required=False)
    password = forms.CharField(label="初始密码", min_length=6, widget=forms.PasswordInput)
    role = forms.ChoiceField(
        label="角色", choices=[("buyer", "核价人员"), ("admin", "管理员")], initial="buyer"
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("该账号已存在")
        return username


class UserUpdateForm(BootstrapMixin, forms.Form):
    display_name = forms.CharField(label="姓名", max_length=50, required=False)
    role = forms.ChoiceField(
        label="角色", choices=[("buyer", "核价人员"), ("admin", "管理员")]
    )
    is_active = forms.BooleanField(label="启用账号", required=False, initial=True)


class SystemSettingForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = [
            "company_name", "default_markup_rate", "default_deviation_low",
            "default_deviation_high", "usd_rate",
        ]


def ensure_roles():
    """确保系统内置角色分组存在。"""
    Group.objects.get_or_create(name="管理员")
    Group.objects.get_or_create(name="核价人员")
