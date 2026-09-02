from django.contrib import admin

from .models import Parent


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ("user", "relationship", "organization", "is_active")
    list_filter = ("relationship", "is_active", "organization")
    search_fields = ("user__username", "user__first_name", "user__last_name")
