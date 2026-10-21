from django.http import HttpResponse
from django.urls import reverse

NAV_SECTIONS = [
    {
        "title": "工作台",
        "items": [{"key": "dashboard", "label": "核价概览", "icon": "bi-grid-1x2", "url": "pricing:dashboard"}],
    },
    {
        "title": "业务处理",
        "items": [
            {"key": "calc", "label": "采购成本核算", "icon": "bi-calculator", "url": "pricing:calc_list"},
            {"key": "quote", "label": "供应商报价", "icon": "bi-file-earmark-text", "url": "pricing:quote_list"},
            {"key": "analysis", "label": "历史与分析", "icon": "bi-graph-up", "url": "pricing:analysis"},
        ],
    },
    {
        "title": "基础数据",
        "items": [
            {"key": "material", "label": "原材料与价格", "icon": "bi-layers", "url": "pricing:material_list"},
            {"key": "part", "label": "零件信息", "icon": "bi-box-seam", "url": "pricing:part_list"},
            {"key": "rule", "label": "成本规则", "icon": "bi-sliders", "url": "pricing:rule_list"},
            {"key": "supplier", "label": "供应商档案", "icon": "bi-truck", "url": "pricing:supplier_list"},
        ],
    },
    {
        "title": "系统",
        "items": [
            {"key": "system", "label": "系统设置", "icon": "bi-gear", "url": "pricing:system"},
            {"key": "audit", "label": "登录审计", "icon": "bi-shield-check", "url": "pricing:audit_log"},
        ],
        "admin_only": True,
    },
]

NAV_MAP = {
    "dashboard": "dashboard",
    "calc_list": "calc",
    "calc_create": "calc",
    "calc_detail": "calc",
    "quote_list": "quote",
    "quote_create": "quote",
    "quote_edit": "quote",
    "analysis": "analysis",
    "material_list": "material",
    "material_create": "material",
    "material_edit": "material",
    "material_detail": "material",
    "part_list": "part",
    "part_create": "part",
    "part_edit": "part",
    "part_detail": "part",
    "rule_list": "rule",
    "rule_create": "rule",
    "rule_edit": "rule",
    "supplier_list": "supplier",
    "supplier_create": "supplier",
    "supplier_edit": "supplier",
    "system": "system",
    "user_create": "system",
    "user_edit": "system",
    "audit_log": "audit",
}


def navigation(request):
    match = request.resolver_match
    active = NAV_MAP.get(match.url_name) if match else None
    sections = []
    for section in NAV_SECTIONS:
        if section.get("admin_only") and not (
            request.user.is_authenticated and request.user.is_superuser
        ):
            continue
        items = []
        for item in section["items"]:
            items.append({**item, "url": reverse(item["url"])})
        sections.append({**section, "items": items})

    role = "访客"
    display_name = ""
    if request.user.is_authenticated:
        role = "管理员" if request.user.is_superuser else "核价人员"
        display_name = request.user.get_full_name() or request.user.username

    return {
        "nav_sections": sections,
        "active_nav": active,
        "current_role": role,
        "display_name": display_name,
    }
