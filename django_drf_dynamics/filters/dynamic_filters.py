from collections import OrderedDict

import django_filters.rest_framework as filters


class DrfDynamicFilterBackend(filters.DjangoFilterBackend):

    TYPE_MAPPING = {
        "date": filters.DateFilter,
        "bool": filters.BooleanFilter,
        "autocomplete": filters.CharFilter,
        "form_value": filters.CharFilter,
        "select": filters.ChoiceFilter,
        "range": filters.RangeFilter,
    }

    def get_filterset_class(self, view, queryset=None):

        class DynamicFilterSet(filters.FilterSet):
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
                # We check that the lookup_expr is not None
                # Because it can be None as done in 'cbs.api._utils.dynamic_filters'
                if lookup_expr:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(
                        field_name=field_name, lookup_expr=lookup_expr
                    )
                else:
                    DynamicFilterSet.base_filters[metadata["name"]] = mapped_field(field_name=field_name)

        # We set the dynamic filterset class to the view
        view.filterset_class = DynamicFilterSet

        # Then we call the super class logics
        return super().get_filterset_class(view, queryset=queryset)
