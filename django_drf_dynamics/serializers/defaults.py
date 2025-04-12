from rest_framework import serializers


class ObjectsLookupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    lookup_icon = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_image = serializers.ImageField(allow_null=True)
    lookup_title = serializers.SerializerMethodField()
    lookup_subtitle = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_description = serializers.CharField(allow_null=True, allow_blank=True)
    lookup_has_image_or_icon = serializers.SerializerMethodField()

    def get_lookup_has_image_or_icon(self, obj):
        return hasattr(obj, "lookup_image") or hasattr(obj, "lookup_icon")

    def get_lookup_title(self, obj):
        return getattr(obj, "lookup_title", obj.__str__())
