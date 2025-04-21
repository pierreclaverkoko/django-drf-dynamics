from collections import OrderedDict

import django_filters.rest_framework as filters


class DrfDynamicFilterBackend(filters.DjangoFilterBackend):
    """
    A custom filter backend for dynamically generating filters based on metadata.

    This backend allows you to define filters dynamically using metadata provided
    in the view's `filterset_metadata` attribute. It supports various filter types
    such as date, boolean, autocomplete, select, and range filters.

    Example usage:

    ```python
    class ExampleViewSet(viewsets.ModelViewSet):
        queryset = ExampleModel.objects.all()
        filter_backends = [DrfDynamicFilterBackend]
        filterset_metadata = [
            {"name": "created_at", "type": "date", "data": {"lookup_expr": "gte"}},
            {"name": "is_active", "type": "bool"},
            {"name": "category", "type": "select", "data": {"choices": [(1, "Category 1"), (2, "Category 2")]}},
        ]
    ```

    Attributes:
        TYPE_MAPPING (dict): A mapping of filter types to their corresponding
            Django Filter classes.
    """

    TYPE_MAPPING = {
        "date": filters.DateFilter,
        "bool": filters.BooleanFilter,
        "autocomplete": filters.CharFilter,
        "form_value": filters.CharFilter,
        "select": filters.ChoiceFilter,
        "range": filters.RangeFilter,
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
            data = metadata["data"] if metadata["data"] else {}

            # Find the field name
            field_name = data.get("field_name", metadata["name"])
            DynamicFilterSet.Meta.fields.append(field_name)

            # Find the right lookup expression
            lookup_expr = data.get("lookup_expr", None)

            if metadata["type"] == "select":
                choices = metadata["data"].get("choices", [])
                DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(field_name=field_name, choices=choices)
            else:
                # Ensure the lookup expression is not None
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
