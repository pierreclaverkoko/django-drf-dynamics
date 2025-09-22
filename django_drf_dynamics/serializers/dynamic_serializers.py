from rest_framework import serializers


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed, and an optional `exclude`
    argument to exclude specific fields.

    This serializer allows dynamic field selection at runtime, which is useful
    for API optimization and providing different views of the same model.

    Example usage:

    ```python
    class UserSerializer(DynamicFieldsModelSerializer):
        class Meta:
            model = User
            fields = '__all__'

    # Usage in view:
    serializer = UserSerializer(user, fields=('id', 'username', 'email'))

    # Or with context:
    serializer = UserSerializer(user, context={'fields': ('id', 'username')})

    # Or with exclude:
    serializer = UserSerializer(user, exclude=('password', 'last_login'))
    ```

    The fields can be specified in multiple ways:
    1. As a parameter during serializer instantiation
    2. Via the context dictionary
    3. Via query parameters (if used with DynamicFieldsMixin in views)
    """

    def __init__(self, *args, **kwargs):
        # Extract fields and exclude arguments
        fields = kwargs.pop("fields", None)
        exclude = kwargs.pop("exclude", None)

        # Don't pass these kwargs to the superclass
        super().__init__(*args, **kwargs)

        # Get fields from context if not provided directly
        if fields is None:
            fields = self.context.get("fields")
        if exclude is None:
            exclude = self.context.get("exclude")

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        elif exclude is not None:
            # Drop fields that are specified in the `exclude` argument.
            excluded = set(exclude)
            for field_name in excluded:
                self.fields.pop(field_name, None)


class DynamicFieldsSerializer(serializers.Serializer):
    """
    A Serializer that takes an additional `fields` argument that
    controls which fields should be displayed, and an optional `exclude`
    argument to exclude specific fields.

    This is similar to DynamicFieldsModelSerializer but for regular Serializers.

    Example usage:

    ```python
    class UserDataSerializer(DynamicFieldsSerializer):
        id = serializers.IntegerField()
        username = serializers.CharField()
        email = serializers.EmailField()
        profile = serializers.DictField()

    # Usage:
    serializer = UserDataSerializer(data, fields=('id', 'username'))
    ```
    """

    def __init__(self, *args, **kwargs):
        # Extract fields and exclude arguments
        fields = kwargs.pop("fields", None)
        exclude = kwargs.pop("exclude", None)

        # Don't pass these kwargs to the superclass
        super().__init__(*args, **kwargs)

        # Get fields from context if not provided directly
        if fields is None:
            fields = self.context.get("fields")
        if exclude is None:
            exclude = self.context.get("exclude")

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        elif exclude is not None:
            # Drop fields that are specified in the `exclude` argument.
            excluded = set(exclude)
            for field_name in excluded:
                self.fields.pop(field_name, None)
