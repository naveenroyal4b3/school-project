from django.urls import path

from .views import (
    FeePaymentDetailView,
    FeePaymentListCreateView,
    FeeStructureDetailView,
    FeeStructureListCreateView,
    PaymentMethodListView,
    ReceiptView,
    StudentFeeSummaryView,
)

urlpatterns = [
    path("", FeeStructureListCreateView.as_view(), name="feestructure-list"),
    path("methods/", PaymentMethodListView.as_view(), name="payment-methods"),
    path("<int:pk>/", FeeStructureDetailView.as_view(), name="feestructure-detail"),

    path("payments/", FeePaymentListCreateView.as_view(), name="feepayment-list"),
    path("payments/<int:pk>/", FeePaymentDetailView.as_view(), name="feepayment-detail"),
    path("payments/<int:pk>/receipt/", ReceiptView.as_view(), name="feepayment-receipt"),

    path("students/<int:student_id>/summary/", StudentFeeSummaryView.as_view(), name="fee-summary"),
]
