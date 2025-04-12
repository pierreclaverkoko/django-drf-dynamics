from django.utils.translation import gettext as _
from rest_framework import serializers


class CheckPasswordSerializerMixin(serializers.Serializer):
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_password(self, value):
        request = self.context.get("request", None)

        if request:
            user = request.user
            if user.is_authenticated:
                if user.check_password(value):
                    return value
            raise serializers.ValidationError(_("Invalid password"))
        else:
            raise serializers.ValidationError(_("Wrong configuration for password verification"))
