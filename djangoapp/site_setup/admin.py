from django.contrib import admin
from site_setup.models import MenuLink, SiteSetup


class MenuLinkInline(admin.TabularInline):
    model = MenuLink
    extra = 1


@admin.register(SiteSetup)
class SiteSetupAdmin(admin.ModelAdmin):
    list_display = 'title', 'description',
    inlines = MenuLinkInline,

    def has_add_permission(self, request) -> bool:
        return not SiteSetup.objects.all()[:1].exists()
