from django.db.models import Avg
from rest_framework import generics
from rest_framework.response import Response

from apps.accounts.models import User
from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly, IsFacultyOrAdmin
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians

from .models import Exam, ExamSchedule, Result
from .serializers import ExamScheduleSerializer, ExamSerializer, ResultSerializer


class ExamListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsFacultyOrAdmin]


class ExamDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsFacultyOrAdmin]


class ExamScheduleListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = ExamSchedule.objects.select_related("exam", "subject").all()
    serializer_class = ExamScheduleSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "exam__organization"


class ExamScheduleDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ExamSchedule.objects.select_related("exam", "subject").all()
    serializer_class = ExamScheduleSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "exam__organization"


class ResultListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    """Faculty enter marks; students and parents read them.

    Unpublished results are hidden from everyone except faculty and admins, so
    a partially entered mark sheet never leaks.
    """

    queryset = Result.objects.select_related(
        "student", "exam_schedule__subject", "exam_schedule__exam"
    ).all()
    serializer_class = ResultSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"

    def get_queryset(self):
        queryset = super().get_queryset()

        user = self.request.user
        staff_roles = (User.Role.SUPER_ADMIN, User.Role.ORGANIZATION_ADMIN, User.Role.TEACHER)
        if not user.is_superuser and user.role not in staff_roles:
            queryset = queryset.filter(exam_schedule__exam__is_published=True)

        student = self.request.query_params.get("student")
        if student:
            queryset = queryset.filter(student_id=student)

        return queryset


class ResultDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Result.objects.select_related("student", "exam_schedule").all()
    serializer_class = ResultSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"


class PublishResultsView(OrganizationScopedMixin, generics.GenericAPIView):
    """Publish an exam and alert every affected guardian."""

    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsAdminOrReadOnly]

    def post(self, request, *args, **kwargs):
        exam = self.get_object()

        if not exam.is_published:
            exam.is_published = True
            exam.save(update_fields=["is_published"])

            students = {
                result.student
                for result in Result.objects.filter(
                    exam_schedule__exam=exam
                ).select_related("student__parent__user", "student__user")
            }
            for student in students:
                notify_guardians(
                    student,
                    title="Exam results published",
                    message=f"Results for {exam.name} are now available.",
                    notification_type=Notification.Type.EXAM,
                )

        return Response(self.get_serializer(exam).data)


class StudentPerformanceView(generics.GenericAPIView):
    """The document's "View Student Performance"."""

    serializer_class = ResultSerializer
    permission_classes = [IsFacultyOrAdmin]

    def get(self, request, student_id, *args, **kwargs):
        results = Result.objects.filter(student_id=student_id).select_related(
            "exam_schedule__subject", "exam_schedule__exam"
        )

        user = request.user
        if not user.is_superuser and user.organization_id is not None:
            results = results.filter(student__organization_id=user.organization_id)

        staff_roles = (User.Role.SUPER_ADMIN, User.Role.ORGANIZATION_ADMIN, User.Role.TEACHER)
        if not user.is_superuser and user.role not in staff_roles:
            results = results.filter(exam_schedule__exam__is_published=True)

        results = list(results)
        total_percentage = sum((r.percentage for r in results), 0)
        count = len(results)

        return Response(
            {
                "student": student_id,
                "papers_taken": count,
                "papers_passed": sum(1 for r in results if r.is_pass),
                "average_percentage": round(total_percentage / count, 2) if count else 0,
                "average_marks": results and round(
                    Result.objects.filter(pk__in=[r.pk for r in results]).aggregate(
                        avg=Avg("marks_obtained")
                    )["avg"] or 0,
                    2,
                ) or 0,
                "results": ResultSerializer(results, many=True).data,
            }
        )
