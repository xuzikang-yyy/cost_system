from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value, digits=2):
    """千分位金额：1234.5 -> 1,234.50"""
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "-"
    if digits == 4:
        return f"{number:,.4f}"
    return f"{number:,.2f}"


@register.filter
def signed(value, digits=2):
    """带符号的金额或百分比数值。"""
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "-"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.{digits}f}"


@register.filter
def absnum(value):
    try:
        return abs(Decimal(value))
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def percent(value, digits=2):
    """将比例数值格式化为百分数，如 0.256 -> 25.60%"""
    try:
        number = Decimal(value) * 100
    except (InvalidOperation, TypeError, ValueError):
        return "-"
    return f"{number:,.{digits}f}%"


@register.filter
def sub(value, arg):
    try:
        return Decimal(value) - Decimal(arg)
    except (InvalidOperation, TypeError, ValueError):
        return 0


@register.filter
def div(value, arg):
    try:
        return Decimal(value) / Decimal(arg)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def mul(value, arg):
    try:
        return Decimal(value) * Decimal(arg)
    except (InvalidOperation, TypeError, ValueError):
        return 0


@register.filter
def adjust(value, rate):
    """按百分比调整金额：value × (1 + rate/100)"""
    try:
        return Decimal(value) * (Decimal("1") + Decimal(rate) / Decimal("100"))
    except (InvalidOperation, TypeError, ValueError):
        return 0


@register.filter
def get_item(mapping, key):
    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


@register.filter
def level_class(level):
    return {"high": "danger", "low": "warning", "normal": "success"}.get(level, "secondary")


@register.filter
def level_text(level):
    return {"high": "偏高", "low": "偏低", "normal": "正常"}.get(level, "待核价")


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """在保留现有筛选条件的基础上生成分页链接参数。"""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        params[key] = value
    encoded = params.urlencode()
    return f"{encoded}&" if encoded else ""

