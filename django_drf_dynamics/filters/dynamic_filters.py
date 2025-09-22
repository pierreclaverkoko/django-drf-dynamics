from collections import OrderedDict

import django_filters.rest_framework as filters


class DrfDynamicFilterBackend(filters.DjangoFilterBackend):
    """
    A custom filter backend for dynamically generating filters based on metadata.

    This backend allows you to define filters dynamically using metadata provided
    in the view's `filterset_metadata` attribute. It supports various filter types
    such as date, boolean, autocomplete, select, range, text search, numeric, and JSON filters.

    Example usage:

    ```python
    class ExampleViewSet(viewsets.ModelViewSet):
        queryset = ExampleModel.objects.all()
        filter_backends = [DrfDynamicFilterBackend]
        filterset_metadata = [
            {"name": "created_at", "type": "date", "data": {"lookup_expr": "gte"}},
            {"name": "is_active", "type": "bool"},
            {"name": "category", "type": "select", "data": {"choices": [(1, "Category 1"), (2, "Category 2")]}},
            {"name": "price", "type": "numeric", "data": {"lookup_expr": "gte", "operator": "gte"}},
            {"name": "name", "type": "text_search", "data": {"lookup_expr": "icontains"}},
            {"name": "metadata", "type": "json", "data": {"lookup_expr": "has_key", "key": "status"}},
        ]
    ```

    Attributes:
        TYPE_MAPPING (dict): A mapping of filter types to their corresponding
            Django Filter classes.
    """

    TYPE_MAPPING = {
        "date": filters.DateFilter,
        "datetime": filters.DateTimeFilter,
        "bool": filters.BooleanFilter,
        "boolean": filters.BooleanFilter,
        "autocomplete": filters.CharFilter,
        "form_value": filters.CharFilter,
        "text_search": filters.CharFilter,
        "select": filters.ChoiceFilter,
        "select_multiple": filters.MultipleChoiceFilter,
        "range": filters.RangeFilter,
        "numeric": filters.NumberFilter,
        "number": filters.NumberFilter,
        "json": filters.CharFilter,  # Custom handling in get_filterset_class
        "geographic": filters.CharFilter,  # Custom handling for geographic filters
        "uuid": filters.UUIDFilter,
        "time": filters.TimeFilter,
        "duration": filters.DurationFilter,
    }

    def get_filterset_class(self, view, queryset=None):
        """
        Dynamically generate a filterset class based on the view's metadata.

        This method creates a `FilterSet` class with filters defined in the
        `filterset_metadata` attribute of the view. The generated filterset
        class is then assigned to the view's `filterset_class` attribute.

        Args:
            view: The view instance that is using this filter backend.
            queryset: The queryset to be filtered.

        Returns:
            FilterSet: A dynamically generated filterset class.
        """

        class DynamicFilterSet(filters.FilterSet):
            """
            A dynamically generated filterset class.

            This class is created at runtime based on the metadata provided
            in the view's `filterset_metadata` attribute.
            """

            base_filters = OrderedDict()

            class Meta:
                model = queryset.model
                fields = []

        filterset_metadata = getattr(view, "filterset_metadata", [])

        for metadata in filterset_metadata:
            mapped_field = self.TYPE_MAPPING.get(metadata["type"])
            data = metadata.get("data", {})

            # Find the field name
            field_name = data.get("field_name", metadata["name"])
            DynamicFilterSet.Meta.fields.append(field_name)

            # Find the right lookup expression
            lookup_expr = data.get("lookup_expr", None)

            # Handle special filter types
            if metadata["type"] in ["select", "select_multiple"]:
                choices = data.get("choices", [])
                DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(field_name=field_name, choices=choices)
            elif metadata["type"] == "json":
                # Custom JSON field filtering
                json_key = data.get("key")
                if json_key and lookup_expr == "has_key":
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr="has_key"
                    )
                elif json_key and lookup_expr == "contains":
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=f"{field_name}__{json_key}", lookup_expr="icontains"
                    )
                else:
                    # Default JSON filtering
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr or "icontains"
                    )
            elif metadata["type"] == "geographic":
                # Geographic filtering (distance, bbox, etc.)
                geo_type = data.get("geo_type", "distance")
                if geo_type == "distance":
                    # For distance-based filtering
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr="distance_lte"
                    )
                elif geo_type == "bbox":
                    # For bounding box filtering
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr="bbcontains"
                    )
                else:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr or "exact"
                    )
            elif metadata["type"] == "numeric":
                # Enhanced numeric filtering with operators
                operator = data.get("operator", "exact")
                valid_operators = ["exact", "lt", "lte", "gt", "gte", "range", "in"]
                if operator in valid_operators:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=operator
                    )
                else:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr or "exact"
                    )
            elif metadata["type"] == "text_search":
                # Enhanced text search with multiple operators
                search_type = data.get("search_type", "icontains")
                valid_search_types = ["icontains", "iexact", "istartswith", "iendswith", "regex", "iregex"]
                if search_type in valid_search_types:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=search_type
                    )
                else:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr or "icontains"
                    )
            else:
                # Default handling for other filter types
                if lookup_expr:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr
                    )
                else:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(field_name=field_name)

        # Assign the dynamic filterset class to the view
        view.filterset_class = DynamicFilterSet

        # Call the parent class logic
        return super().get_filterset_class(view, queryset=queryset)
