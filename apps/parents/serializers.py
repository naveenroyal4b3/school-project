from rest_framework import serializers

from .models import Parent


class ParentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Parent
        fields = "__all__"
