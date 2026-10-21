from django.contrib import admin

from .models import (
    CostCalculation,
    CostCalculationDetail,
    CostRule,
    LoginAudit,
    Material,
    MaterialPrice,
    Part,
    Supplier,
    SupplierQuote,
    SystemSetting,
)


class MaterialPriceInline(admin.TabularInline):
    model = MaterialPrice
    extra = 0


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "material_type", "unit", "status")
    search_fields = ("code", "name")
    inlines = [MaterialPriceInline]


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "material", "net_weight", "status")
    list_filter = ("category", "status")
    search_fields = ("code", "name")


@admin.register(CostRule)
class CostRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "version", "loss_rate", "markup_rate", "is_active")
    list_filter = ("category", "is_active")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "contact", "status")
    list_filter = ("category", "status")


@admin.register(SupplierQuote)
class SupplierQuoteAdmin(admin.ModelAdmin):
    list_display = ("part", "supplier", "unit_price", "price_unit", "quote_date", "normalized_price")
    list_filter = ("supplier", "price_unit", "tax_included")
    search_fields = ("part__name", "supplier__name")


class DetailInline(admin.TabularInline):
    model = CostCalculationDetail
    extra = 0


@admin.register(CostCalculation)
class CostCalculationAdmin(admin.ModelAdmin):
    list_display = ("calc_no", "part", "status", "unit_cost", "reference_price", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("calc_no", "part__name")
    inlines = [DetailInline]


admin.site.register(SystemSetting)


@admin.register(LoginAudit)
class LoginAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "username", "ip", "user_agent")
    list_filter = ("event", "created_at")
    search_fields = ("username", "ip", "user_agent")
    readonly_fields = ("username", "user", "event", "ip", "user_agent", "created_at")
admin.site.site_header = "采购成本核价系统后台"
admin.site.site_title = "采购成本核价系统"
