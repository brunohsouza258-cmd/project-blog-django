from django.contrib import admin

from blog.models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = 'name', 'slug',
    search_fields = 'name',
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = 'title', 'category', 'is_published', 'published_at',
    list_display_links = 'title',
    list_editable = 'is_published',
    list_filter = 'is_published', 'category', 'published_at',
    search_fields = 'title', 'excerpt', 'content',
    date_hierarchy = 'published_at'
    # Preenche o slug enquanto você digita o título.
    prepopulated_fields = {'slug': ('title',)}
    list_per_page = 25
    actions = 'publish', 'unpublish',

    @admin.action(description='Publicar posts selecionados')
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description='Voltar para rascunho')
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)

    def save_model(self, request, obj, form, change):
        # Guarda quem criou o post (você, logado no admin).
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
