from django.contrib import admin
from site_setup.models import MenuLink, SiteSetup


# Inline: mostra os MenuLinks dentro da própria página do Setup no admin,
# em formato de tabela. "extra = 1" deixa uma linha vazia pronta para
# cadastrar um link novo.
class MenuLinkInline(admin.TabularInline):
    model = MenuLink
    extra = 1


@admin.register(SiteSetup)
class SiteSetupAdmin(admin.ModelAdmin):
    list_display = 'title', 'description',
    inlines = MenuLinkInline,

    # Garante que exista só UM Setup: o botão "Adicionar" some do admin
    # assim que o primeiro for criado. [:1].exists() faz uma consulta
    # leve (LIMIT 1) em vez de contar todos os registros.
    def has_add_permission(self, request) -> bool:
        return not SiteSetup.objects.all()[:1].exists()
