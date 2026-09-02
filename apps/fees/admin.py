from django.contrib import admin

from .models import FeePayment, FeeStructure


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "frequency", "due_date", "organization", "is_active")
    list_filter = ("frequency", "is_active")


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "student", "amount_paid", "payment_method", "status")
    list_filter = ("payment_method", "status")
    search_fields = ("receipt_number", "transaction_id", "student__admission_no")
