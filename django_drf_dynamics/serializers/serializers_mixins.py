from django.utils.translation import gettext as _
from rest_framework import serializers


class CheckPasswordSerializerMixin(serializers.Serializer):
    """
    A serializer mixin to validate a user's password.

    This mixin provides a `password` field and a method to validate the password
    against the authenticated user's stored password. It is designed to be used
    in serializers where password verification is required.

    Attributes:
        password (CharField): A write-only field for the user's password with a
            minimum length of 8 characters.
    """

    password = serializers.CharField(min_length=8, write_only=True)

    def validate_password(self, value):
        """
        Validate the provided password against the authenticated user's password.

        Args:
            value (str): The password provided by the user.

        Returns:
            str: The validated password if it matches the stored password.

        Raises:
            serializers.ValidationError: If the password is invalid or if the
            request context is not properly configured.
        """
        request = self.context.get("request", None)

        if request:
            user = request.user
            if user.is_authenticated:
                if user.check_password(value):
                    return value
            raise serializers.ValidationError(_("Invalid password"))
        else:
            raise serializers.ValidationError(_("Wrong configuration for password verification"))
