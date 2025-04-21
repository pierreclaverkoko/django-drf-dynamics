from rest_framework import serializers


class ObjectsLookupSerializer(serializers.Serializer):
    """
    A serializer for providing a standardized lookup representation of objects.

    This serializer is designed to be used for object lookups in APIs, providing
    fields such as `id`, `lookup_icon`, `lookup_image`, `lookup_title`, and more.
    It also includes methods to dynamically compute certain fields.

    Fields:
        id (IntegerField): The unique identifier of the object.
        lookup_icon (CharField): An optional icon representation of the object.
        lookup_image (ImageField): An optional image representation of the object.
        lookup_title (SerializerMethodField): The title of the object, computed dynamically.
        lookup_subtitle (CharField): An optional subtitle for the object.
        lookup_description (CharField): An optional description of the object.
        lookup_has_image_or_icon (SerializerMethodField): A boolean indicating if the object
            has either an image or an icon.
    """

    id = serializers.IntegerField()
    lookup_icon = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_image = serializers.ImageField(allow_null=True)
    lookup_title = serializers.SerializerMethodField()
    lookup_subtitle = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_description = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_has_image_or_icon = serializers.SerializerMethodField()

    def get_lookup_has_image_or_icon(self, obj):
        """
        Determine if the object has either an image or an icon.

        Args:
            obj: The object being serialized.

        Returns:
            bool: True if the object has an image or an icon, False otherwise.
        """
        return hasattr(obj, "lookup_image") or hasattr(obj, "lookup_icon")

    def get_lookup_title(self, obj):
        """
        Get the title of the object.

        This method attempts to retrieve the `lookup_title` attribute of the object.
        If not available, it defaults to the string representation of the object.

        Args:
            obj: The object being serialized.

        Returns:
            str: The title of the object.
        """
        return getattr(obj, "lookup_title", obj.__str__())
