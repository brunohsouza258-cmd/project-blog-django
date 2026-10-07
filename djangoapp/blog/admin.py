from django.contrib import admin

from blog.models import Category, Comment, Like, Post


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


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = 'author', 'post', 'short_text', 'created_at', 'is_visible',
    list_editable = 'is_visible',
    list_filter = 'is_visible', 'created_at',
    search_fields = 'text', 'author__first_name', 'author__email', 'post__title',
    list_select_related = 'author', 'post',
    readonly_fields = 'post', 'author', 'text', 'created_at',
    actions = 'hide', 'show',

    @admin.display(description='Comentário')
    def short_text(self, obj):
        return obj.text[:80]

    @admin.action(description='Esconder comentários selecionados')
    def hide(self, request, queryset):
        queryset.update(is_visible=False)

    @admin.action(description='Mostrar comentários selecionados')
    def show(self, request, queryset):
        queryset.update(is_visible=True)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = 'user', 'post', 'created_at',
    list_filter = 'created_at',
    search_fields = 'user__first_name', 'user__email', 'post__title',
    list_select_related = 'user', 'post',
    readonly_fields = 'user', 'post', 'created_at',
