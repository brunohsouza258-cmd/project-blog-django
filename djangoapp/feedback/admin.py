from django.contrib import admin
from feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = 'name', 'email', 'created_at', 'read',
    list_filter = 'read', 'created_at',
    list_editable = 'read',
    search_fields = 'name', 'email', 'message',
    readonly_fields = 'name', 'email', 'message', 'created_at',
