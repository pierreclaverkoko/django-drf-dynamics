from rest_framework import serializers


class AutocompleteItemSerializer(serializers.Serializer):
    """
    Serializer for individual autocomplete items.

    This serializer provides a standardized format for autocomplete results
    that can be easily consumed by frontend components.
    """

    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(required=False)
    value = serializers.CharField(required=False)

    # Additional metadata
    score = serializers.FloatField(required=False)
    category = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    icon = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.URLField(required=False, allow_null=True)

    # Nested object data
    nested_data = serializers.DictField(required=False)

    def to_representation(self, instance):
        """
        Convert model instance to autocomplete item format.

        Args:
            instance: Model instance or dict

        Returns:
            dict: Serialized autocomplete item
        """
        if isinstance(instance, dict):
            return instance

        # Get display text
        display_field = self._get_display_field()
        text = str(getattr(instance, display_field, instance))

        data = {
            "id": str(instance.id),
            "title": text,
            "subtitle": text,
            "value": str(instance.id),
        }

        # Add score if available
        if hasattr(instance, "_autocomplete_similarity"):
            data["score"] = instance._autocomplete_similarity
        elif hasattr(instance, "_es_score"):
            data["score"] = instance._es_score
        elif hasattr(instance, "_cache_score"):
            data["score"] = instance._cache_score

        # Add category if available
        if hasattr(instance, "get_category"):
            data["category"] = instance.get_category()
        elif hasattr(instance, "category"):
            data["category"] = str(instance.category)

        # Add description if available
        description_fields = ["description", "bio", "summary", "notes"]
        for field in description_fields:
            if hasattr(instance, field):
                field_value = getattr(instance, field, "")
                if field_value:
                    data["description"] = str(field_value)[:200] + ("..." if len(str(field_value)) > 200 else "")
                    break

        # Add icon if available
        icon_fields = ["icon", "icon_name", "fa_icon"]
        for field in icon_fields:
            if hasattr(instance, field):
                field_value = getattr(instance, field, "")
                if field_value:
                    data["icon"] = str(field_value)
                    break

        # Add image URL if available
        image_fields = ["image", "avatar", "photo", "thumbnail"]
        for field in image_fields:
            if hasattr(instance, field):
                field_value = getattr(instance, field)
                if field_value and hasattr(field_value, "url"):
                    data["image_url"] = field_value.url
                    break

        # Add nested data for related objects
        nested_data = self._get_nested_data(instance)
        if nested_data:
            data["nested_data"] = nested_data

        return data

    def _get_display_field(self):
        """
        Get the field to use for display text.

        Returns:
            str: Field name for display
        """
        # Try to get from view configuration
        view = self.context.get("view")
        if view and hasattr(view, "autocomplete_display_field") and view.autocomplete_display_field:
            return view.autocomplete_display_field

        # Default fields to try
        display_fields = ["name", "title", "label", "text", "__str__"]

        return display_fields[0]  # Default to 'name'

    def _get_nested_data(self, instance):
        """
        Extract nested/related object data.

        Args:
            instance: Model instance

        Returns:
            dict: Nested data or None
        """
        view = self.context.get("view")
        if not view or not hasattr(view, "nested_lookup_fields"):
            return None

        nested_data = {}

        for field_name, config in view.nested_lookup_fields.items():
            if hasattr(instance, field_name):
                related_obj = getattr(instance, field_name)
                if related_obj:
                    nested_data[field_name] = {
                        "id": getattr(related_obj, "id", None),
                        "text": str(related_obj),
                        "fields": {},
                    }

                    # Add configured fields
                    for field in config.get("fields", []):
                        if hasattr(related_obj, field):
                            nested_data[field_name]["fields"][field] = str(getattr(related_obj, field, ""))

        return nested_data if nested_data else None


class AutocompleteResponseSerializer(serializers.Serializer):
    """
    Serializer for complete autocomplete response.

    This serializer structures the response from autocomplete endpoints
    including results and metadata.
    """

    results = AutocompleteItemSerializer(many=True)
    metadata = serializers.DictField()

    def to_representation(self, instance):
        """
        Handle different input formats for the response.

        Args:
            instance: Response data

        Returns:
            dict: Serialized response
        """
        if isinstance(instance, dict):
            return instance

        return super().to_representation(instance)


class AutocompleteMetadataSerializer(serializers.Serializer):
    """
    Serializer for autocomplete metadata.

    Provides information about the search operation and configuration.
    """

    query = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField(required=False)
    min_length = serializers.IntegerField(required=False)
    search_time_ms = serializers.FloatField(required=False)
    backend = serializers.CharField(required=False)
    fuzzy_enabled = serializers.BooleanField(required=False)
    fields_searched = serializers.ListField(child=serializers.CharField(), required=False)
    cached = serializers.BooleanField(required=False)
    cache_timeout = serializers.IntegerField(required=False)
    cache_key = serializers.CharField(required=False)
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class AutocompleteConfigurationSerializer(serializers.Serializer):
    """
    Serializer for autocomplete configuration.

    Provides frontend with all necessary configuration details
    for implementing autocomplete functionality.
    """

    fields = serializers.ListField(child=serializers.CharField())
    display_field = serializers.CharField()
    min_length = serializers.IntegerField()
    max_results = serializers.IntegerField()
    fuzzy_enabled = serializers.BooleanField()
    fuzzy_threshold = serializers.FloatField()
    case_sensitive = serializers.BooleanField()
    backend = serializers.CharField()

    # Endpoint information
    endpoints = serializers.DictField()

    # Frontend guidance
    debounce_recommended_ms = serializers.IntegerField()
    example_usage = serializers.DictField()

    # Field-specific configuration
    field_configs = serializers.DictField(required=False)

    # Nested lookup configuration
    nested_fields = serializers.DictField(required=False)


class FieldConfigurationSerializer(serializers.Serializer):
    """
    Serializer for individual field configuration.

    Used within AutocompleteConfigurationSerializer for field-specific settings.
    """

    weight = serializers.FloatField()
    search_type = serializers.CharField()
    boost_exact = serializers.FloatField()
    boost_startswith = serializers.FloatField()
    fuzzy = serializers.BooleanField()
    case_sensitive = serializers.BooleanField()


class NestedLookupConfigurationSerializer(serializers.Serializer):
    """
    Serializer for nested lookup configuration.

    Defines how nested/related objects should be searched and displayed.
    """

    model = serializers.CharField()
    fields = serializers.ListField(child=serializers.CharField())
    display_format = serializers.CharField()
    max_depth = serializers.IntegerField(default=3)


class AutocompleteCacheInfoSerializer(serializers.Serializer):
    """
    Serializer for cache information in responses.

    Provides details about caching status and configuration.
    """

    enabled = serializers.BooleanField()
    hit = serializers.BooleanField(required=False)
    key = serializers.CharField(required=False)
    timeout = serializers.IntegerField(required=False)
    created_at = serializers.DateTimeField(required=False)
    expires_at = serializers.DateTimeField(required=False)


class AutocompleteStatsSerializer(serializers.Serializer):
    """
    Serializer for autocomplete performance statistics.

    Useful for monitoring and optimization.
    """

    total_searches = serializers.IntegerField()
    cache_hits = serializers.IntegerField()
    cache_misses = serializers.IntegerField()
    average_search_time_ms = serializers.FloatField()
    popular_queries = serializers.ListField(child=serializers.DictField())
    backend_usage = serializers.DictField()

    def to_representation(self, instance):
        """
        Calculate derived statistics.

        Args:
            instance: Stats data

        Returns:
            dict: Calculated statistics
        """
        data = super().to_representation(instance)

        # Calculate cache hit rate
        total_cache_requests = data.get("cache_hits", 0) + data.get("cache_misses", 0)
        if total_cache_requests > 0:
            data["cache_hit_rate"] = data.get("cache_hits", 0) / total_cache_requests
        else:
            data["cache_hit_rate"] = 0.0

        return data


class BulkAutocompleteRequestSerializer(serializers.Serializer):
    """
    Serializer for bulk autocomplete requests.

    Allows multiple queries to be processed in a single request.
    """

    queries = serializers.ListField(child=serializers.CharField(), min_length=1, max_length=10)  # Limit bulk requests
    limit = serializers.IntegerField(min_value=1, max_value=100, default=10)
    fuzzy = serializers.BooleanField(default=False)
    fields = serializers.ListField(child=serializers.CharField(), required=False)


class BulkAutocompleteResponseSerializer(serializers.Serializer):
    """
    Serializer for bulk autocomplete responses.

    Returns results for multiple queries.
    """

    results = serializers.DictField()  # Query -> Results mapping
    metadata = serializers.DictField()

    def to_representation(self, instance):
        """
        Structure bulk response data.

        Args:
            instance: Bulk response data

        Returns:
            dict: Structured bulk response
        """
        if not isinstance(instance, dict):
            return instance

        # Ensure results is properly structured
        results = instance.get("results", {})
        metadata = instance.get("metadata", {})

        # Add summary to metadata
        if "summary" not in metadata and results:
            total_results = sum(len(query_results) for query_results in results.values())
            metadata["summary"] = {
                "queries_processed": len(results),
                "total_results": total_results,
                "average_results_per_query": total_results / len(results) if results else 0,
            }

        return {"results": results, "metadata": metadata}


class AutocompleteExportSerializer(serializers.Serializer):
    """
    Serializer for exporting autocomplete data.

    Used for data export functionality.
    """

    format = serializers.ChoiceField(choices=["json", "csv", "excel"], default="json")
    fields = serializers.ListField(child=serializers.CharField(), required=False)
    include_metadata = serializers.BooleanField(default=True)
    max_records = serializers.IntegerField(min_value=1, max_value=10000, default=1000)
