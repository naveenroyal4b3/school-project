from django.contrib import admin

from .models import Attendance, BusAttendance, StudentQRCode


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "subject", "status", "marked_by")
    list_filter = ("status", "date")


admin.site.register([StudentQRCode, BusAttendance])
