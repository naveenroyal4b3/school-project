from django.contrib import admin

from .models import Period, Room, TimetableEntry


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("weekday", "period", "classroom", "subject", "teacher", "room")
    list_filter = ("weekday", "classroom")


admin.site.register([Room, Period])
