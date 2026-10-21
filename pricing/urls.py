from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    # 原材料
    path("materials/", views.material_list, name="material_list"),
    path("materials/new/", views.material_create, name="material_create"),
    path("materials/<int:pk>/", views.material_detail, name="material_detail"),
    path("materials/<int:pk>/edit/", views.material_edit, name="material_edit"),
    # 零件
    path("parts/", views.part_list, name="part_list"),
    path("parts/new/", views.part_create, name="part_create"),
    path("parts/<int:pk>/", views.part_detail, name="part_detail"),
    path("parts/<int:pk>/edit/", views.part_edit, name="part_edit"),
    # 成本规则
    path("rules/", views.rule_list, name="rule_list"),
    path("rules/new/", views.rule_create, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    # 供应商
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:pk>/edit/", views.supplier_edit, name="supplier_edit"),
    # 报价
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/new/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    # 核价
    path("calculations/", views.calc_list, name="calc_list"),
    path("calculations/new/", views.calc_create, name="calc_create"),
    path("calculations/<int:pk>/", views.calc_detail, name="calc_detail"),
    path("calculations/<int:pk>/confirm/", views.calc_confirm, name="calc_confirm"),
    path("calculations/<int:pk>/export/", views.calc_export, name="calc_export"),
    path("calculations/export/", views.calc_export_all, name="calc_export_all"),
    # 分析
    path("analysis/", views.analysis, name="analysis"),
    # 系统
    path("system/", views.system, name="system"),
    path("system/audit/", views.audit_log, name="audit_log"),
    path("system/users/new/", views.user_create, name="user_create"),
    path("system/users/<int:pk>/edit/", views.user_edit, name="user_edit"),
]
