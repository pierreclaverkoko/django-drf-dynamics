from rest_framework import serializers


class ListMetadataSerializer(serializers.Serializer):
    """
    Serializer for list metadata information.

    This serializer structures metadata about list configurations,
    fields, pagination, search, sorting, and filtering options.
    """

    config_name = serializers.CharField()
    fields = serializers.ListField(child=serializers.DictField())
    pagination = serializers.DictField()
    search = serializers.DictField()
    sorting = serializers.DictField()
    filters = serializers.DictField()


class ListConfigurationSerializer(serializers.Serializer):
    """
    Serializer for list configuration data.

    This serializer defines the structure of list configurations
    that can be used to create dynamic list components.
    """

    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True, default="")
    fields = serializers.ListField(child=serializers.CharField())
    per_page = serializers.IntegerField(min_value=1, max_value=1000, default=25)
    per_page_options = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=1000), default=[10, 25, 50, 100]
    )

    # Search configuration
    enable_search = serializers.BooleanField(default=False)
    search_fields = serializers.ListField(child=serializers.CharField(), default=list)
    search_placeholder = serializers.CharField(allow_blank=True, default="Search...")

    # Filtering configuration
    enable_filters = serializers.BooleanField(default=False)
    filter_position = serializers.ChoiceField(choices=["top", "sidebar", "modal"], default="top")

    # Sorting configuration
    enable_sorting = serializers.BooleanField(default=True)
    sorting_fields = serializers.ListField(child=serializers.CharField(), default=list)
    default_ordering = serializers.CharField(allow_blank=True, default="")

    # Display configuration
    display_mode = serializers.ChoiceField(choices=["table", "card", "list"], default="table")
    show_row_numbers = serializers.BooleanField(default=False)
    show_actions = serializers.BooleanField(default=True)

    # Real-time configuration
    enable_realtime = serializers.BooleanField(default=False)
    realtime_events = serializers.ListField(
        child=serializers.ChoiceField(choices=["create", "update", "delete"]), default=["create", "update", "delete"]
    )

    # Cache configuration
    enable_caching = serializers.BooleanField(default=False)
    cache_timeout = serializers.IntegerField(min_value=0, default=300)


class PaginationInfoSerializer(serializers.Serializer):
    """
    Serializer for pagination information.

    Provides pagination metadata for list responses.
    """

    current_page = serializers.IntegerField(min_value=1)
    per_page = serializers.IntegerField(min_value=1)
    total_pages = serializers.IntegerField(min_value=0)
    total_count = serializers.IntegerField(min_value=0)
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()
    next_page = serializers.IntegerField(min_value=1, allow_null=True)
    previous_page = serializers.IntegerField(min_value=1, allow_null=True)


class ListMetaSerializer(serializers.Serializer):
    """
    Serializer for list response metadata.

    Provides metadata about the list configuration and capabilities.
    """

    config_name = serializers.CharField()
    fields = serializers.ListField(child=serializers.CharField())
    search_enabled = serializers.BooleanField()
    filters_enabled = serializers.BooleanField()
    sorting_enabled = serializers.BooleanField()
    realtime_enabled = serializers.BooleanField(default=False)
    backend = serializers.CharField(default="django_orm")


class DynamicListSerializer(serializers.Serializer):
    """
    Serializer for dynamic list responses.

    This serializer structures the complete response for dynamic lists,
    including data, pagination, and metadata.
    """

    data = serializers.ListField(child=serializers.DictField())
    pagination = PaginationInfoSerializer()
    meta = ListMetaSerializer()
    websocket = serializers.DictField(required=False)

    def to_representation(self, instance):
        """
        Custom representation to handle different data structures.

        Args:
            instance: The data instance to serialize

        Returns:
            dict: Serialized representation
        """
        if isinstance(instance, dict):
            return instance

        # Handle QuerySet or list data
        return super().to_representation(instance)


class FieldMetadataSerializer(serializers.Serializer):
    """
    Serializer for field metadata information.

    Describes individual fields in list configurations.
    """

    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField()
    required = serializers.BooleanField(default=False)
    read_only = serializers.BooleanField(default=False)
    help_text = serializers.CharField(allow_blank=True, default="")
    sortable = serializers.BooleanField(default=True)
    filterable = serializers.BooleanField(default=False)
    searchable = serializers.BooleanField(default=False)

    # Display options
    width = serializers.CharField(allow_blank=True, default="auto")
    align = serializers.ChoiceField(choices=["left", "center", "right"], default="left")
    format = serializers.CharField(allow_blank=True, default="")

    # Field-specific options
    choices = serializers.ListField(child=serializers.DictField(), required=False)
    min_value = serializers.FloatField(required=False)
    max_value = serializers.FloatField(required=False)
    max_length = serializers.IntegerField(required=False)


class SortingMetadataSerializer(serializers.Serializer):
    """
    Serializer for sorting metadata.

    Describes available sorting options for list fields.
    """

    name = serializers.CharField()
    label = serializers.CharField()
    asc = serializers.CharField()  # Field name for ascending sort
    desc = serializers.CharField()  # Field name for descending sort
    default = serializers.BooleanField(default=False)


class SearchMetadataSerializer(serializers.Serializer):
    """
    Serializer for search metadata.

    Describes search configuration and capabilities.
    """

    enabled = serializers.BooleanField()
    fields = serializers.ListField(child=serializers.CharField())
    placeholder = serializers.CharField(allow_blank=True)
    search_types = serializers.ListField(
        child=serializers.ChoiceField(choices=["exact", "icontains", "istartswith", "iendswith", "regex"]),
        default=["icontains"],
    )
    min_chars = serializers.IntegerField(min_value=1, default=1)
    debounce_ms = serializers.IntegerField(min_value=0, default=300)


class WebSocketInfoSerializer(serializers.Serializer):
    """
    Serializer for WebSocket connection information.

    Provides details needed to establish WebSocket connections
    for real-time list updates.
    """

    available = serializers.BooleanField()
    group_name = serializers.CharField(required=False)
    url = serializers.CharField(required=False)
    protocols = serializers.ListField(child=serializers.CharField(), default=list)
    events = serializers.ListField(child=serializers.CharField(), default=list)
    connection_instructions = serializers.DictField(required=False)
    error = serializers.CharField(required=False)


class ListActionSerializer(serializers.Serializer):
    """
    Serializer for list action buttons and operations.

    Defines actions that can be performed on list items.
    """

    name = serializers.CharField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=["button", "link", "dropdown"], default="button")
    style = serializers.ChoiceField(
        choices=["primary", "secondary", "success", "danger", "warning", "info"], default="primary"
    )
    icon = serializers.CharField(allow_blank=True, default="")
    url = serializers.CharField(allow_blank=True, default="")
    method = serializers.ChoiceField(choices=["GET", "POST", "PUT", "PATCH", "DELETE"], default="GET")
    confirm = serializers.BooleanField(default=False)
    confirm_message = serializers.CharField(allow_blank=True, default="")
    permissions = serializers.ListField(child=serializers.CharField(), default=list)

    # Bulk action configuration
    bulk_action = serializers.BooleanField(default=False)
    single_action = serializers.BooleanField(default=True)


class BulkActionSerializer(serializers.Serializer):
    """
    Serializer for bulk actions on list items.

    Handles operations that can be performed on multiple selected items.
    """

    action = serializers.CharField()
    item_ids = serializers.ListField(child=serializers.CharField())
    parameters = serializers.DictField(required=False, default=dict)


class ListFilterSerializer(serializers.Serializer):
    """
    Serializer for list filter values.

    Handles filter parameters passed to list endpoints.
    """

    config = serializers.CharField(required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    per_page = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    search = serializers.CharField(allow_blank=True, default="")
    ordering = serializers.CharField(allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add dynamic filter fields based on filterset_metadata
        # This would be populated by the view based on available filters
        self.dynamic_filters = {}

    def to_internal_value(self, data):
        """
        Convert incoming data to internal values, including dynamic filters.

        Args:
            data: Raw request data

        Returns:
            dict: Validated and cleaned data
        """
        validated_data = super().to_internal_value(data)

        # Handle dynamic filter fields
        for key, value in data.items():
            if key not in self.fields and key in self.dynamic_filters:
                validated_data[key] = value

        return validated_data


class ExportConfigurationSerializer(serializers.Serializer):
    """
    Serializer for list export configuration.

    Handles export options for list data.
    """

    format = serializers.ChoiceField(choices=["csv", "excel", "pdf", "json"], default="csv")
    fields = serializers.ListField(child=serializers.CharField(), required=False)
    filename = serializers.CharField(allow_blank=True, default="")
    include_headers = serializers.BooleanField(default=True)
    filters = serializers.DictField(default=dict)
    max_records = serializers.IntegerField(min_value=1, max_value=100000, default=10000)
