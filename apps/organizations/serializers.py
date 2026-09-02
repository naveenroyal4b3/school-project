from rest_framework import serializers

from .branding import vocabulary_for
from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class OrganizationBrandingSerializer(serializers.ModelSerializer):
    """What the front end needs to dress itself as one tenant.

    Deliberately narrow: every signed-in user reads this, including students and
    parents, so it must not carry subscription, billing or contact details that
    only an administrator should see.
    """

    vocabulary = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "organization_name",
            "organization_type",
            "primary_color",
            "secondary_color",
            "logo_url",
            "initials",
            "vocabulary",
        ]

    def get_vocabulary(self, obj):
        return vocabulary_for(obj.organization_type)

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    def get_initials(self, obj):
        """Fallback mark for a tenant that has not uploaded a logo."""
        words = [w for w in obj.organization_name.split() if w[:1].isalnum()]
        return "".join(w[0] for w in words[:2]).upper() or "SS"
