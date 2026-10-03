from django.contrib import admin
from django.utils.html import format_html

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Para moderar: se alguém subir uma foto imprópria, remova por aqui.
    list_display = 'user', 'preview',
    search_fields = 'user__first_name', 'user__email',
    readonly_fields = 'user', 'preview',
    actions = 'remove_avatar',

    @admin.display(description='Foto')
    def preview(self, obj):
        if not obj.avatar:
            return '-'
        return format_html(
            # Sem style="...": a CSP do site bloqueia estilos inline.
            '<img src="{}" width="48" height="48" alt="">',
            obj.avatar.url,
        )

    @admin.action(description='Remover foto dos perfis selecionados')
    def remove_avatar(self, request, queryset):
        for profile in queryset:
            if profile.avatar:
                profile.avatar.delete(save=True)
