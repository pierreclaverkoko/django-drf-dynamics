from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from rest_framework.decorators import action
from rest_framework.response import Response


class DynamicFiltersMixin:
    """
    A mixin to dynamically generate filter metadata for API views.

    This mixin provides utility methods to define various types of filters,
    such as select, autocomplete, boolean, date, datetime, range, and form value filters.
    It also includes an action to return filtering metadata for use in frontend
    applications.

    Example usage:

    ```python
    class AccountViewSet(viewsets.ModelViewSet, DynamicFiltersMixin):
        queryset = Account.objects.all()
        filterset_metadata = [
            DynamicFiltersMixin.filter_autocomplete(
                title=_("Client category"),
                name="client_category",
                url="v1:api:clients:clientcategory-objects-autocomplete",
            ),
            DynamicFiltersMixin.filter_select(
                title=_("Sex"),
                name="individual__sex",
                choices_class=IndividualClientProfile.SexChoice,
            ),
            DynamicFiltersMixin.filter_bool(title=_("Is secret client?"), name="client_is_secret"),
            DynamicFiltersMixin.filter_date(title=_("Creation date"), name="created_at"),
            DynamicFiltersMixin.filter_datetime(title=_("Last updated"), name="updated_at"),
        ]
    ```
    """

    @classmethod
    def filter_select(cls, title, name, choices_class, is_multiple=False, lookup_expr=None):
        """
        Create metadata for a select or multiple select filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            choices_class (Choices): A class containing the choices for the filter.
                Must be a subclass of `models.TextChoices` or `models.IntegerChoices`.
            is_multiple (bool, optional): Whether the filter allows multiple selections. Defaults to False.
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the select filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "select_multiple" if is_multiple else "select",
            "data": {"choices": cls.build_select_choices(choices_class), "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_autocomplete(cls, title, name, url):
        """
        Create metadata for an autocomplete filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            url (str): The URL for the autocomplete endpoint.

        Returns:
            dict: Metadata for the autocomplete filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "autocomplete",
            "data": {"url": reverse_lazy(url)},
        }

    @classmethod
    def filter_client(cls, title=None, name=None):
        """
        Create metadata for a client autocomplete filter.

        Args:
            title (str, optional): The display title of the filter. Defaults to "Client".
            name (str, optional): The name of the filter field. Defaults to "client".

        Returns:
            dict: Metadata for the client autocomplete filter.
        """
        if not title:
            title = _("Client")
        if not name:
            name = "client"
        return cls.filter_autocomplete(title=title, name=name, url="v1:api:clients:bankclient-objects-autocomplete")

    @classmethod
    def filter_client_account(cls, title=None, name=None):
        """
        Create metadata for a client account autocomplete filter.

        Args:
            title (str, optional): The display title of the filter. Defaults to "Account".
            name (str, optional): The name of the filter field. Defaults to "account".

        Returns:
            dict: Metadata for the client account autocomplete filter.
        """
        if not title:
            title = _("Account")
        if not name:
            name = "account"
        return cls.filter_autocomplete(title=title, name=name, url="v1:api:clients:bankaccount-objects-autocomplete")

    @classmethod
    def filter_bool(cls, title, name, lookup_expr=None):
        """
        Create metadata for a boolean filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the boolean filter.
        """
        return {"title": title, "name": name, "type": "bool", "data": {"lookup_expr": lookup_expr}}

    @classmethod
    def filter_form_value(cls, title, name, field_type=None, lookup_expr=None):
        """
        Create metadata for a form value filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            field_type (str, optional): The type of the form field (e.g., "text"). Defaults to "text".
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the form value filter.
        """
        if not field_type:
            field_type = "text"
        return {
            "title": title,
            "name": name,
            "type": "form_value",
            "data": {"field_type": field_type, "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_range(cls, title, name, min_=None, max_=None, step=None, lookup_expr=None):
        """
        Create metadata for a range filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            min_ (int, optional): The minimum value for the range. Defaults to None.
            max_ (int, optional): The maximum value for the range. Defaults to None.
            step (int, optional): The step value for the range. Defaults to 1.
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the range filter.
        """
        if not step:
            step = 1
        return {
            "title": title,
            "name": name,
            "type": "range",
            "data": {"min": min_, "max": max_, "step": step, "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_date(cls, title, name, lookup_expr=None):
        """
        Create metadata for a date filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the date filter.
        """
        return {"title": title, "name": name, "type": "date", "data": {"field_name": name, "lookup_expr": lookup_expr}}

    @classmethod
    def filter_datetime(cls, title, name, lookup_expr=None):
        """
        Create metadata for a datetime filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            lookup_expr (str, optional): The lookup expression for the filter. Defaults to None.

        Returns:
            dict: Metadata for the datetime filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "datetime",
            "data": {"field_name": name, "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_numeric(cls, title, name, operator="exact", min_value=None, max_value=None, step=1):
        """
        Create metadata for a numeric filter with operators.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            operator (str, optional): The numeric operator (exact, gt, gte, lt, lte, range). Defaults to "exact".
            min_value (float, optional): Minimum value for the filter. Defaults to None.
            max_value (float, optional): Maximum value for the filter. Defaults to None.
            step (float, optional): Step value for the filter. Defaults to 1.

        Returns:
            dict: Metadata for the numeric filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "numeric",
            "data": {
                "operator": operator,
                "min_value": min_value,
                "max_value": max_value,
                "step": step,
                "lookup_expr": operator,
            },
        }

    @classmethod
    def filter_text_search(cls, title, name, search_type="icontains", placeholder=None):
        """
        Create metadata for a text search filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter field.
            search_type (str, optional): The search type (icontains, iexact, istartswith, etc.). Defaults to "icontains".
            placeholder (str, optional): Placeholder text for the input. Defaults to None.

        Returns:
            dict: Metadata for the text search filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "text_search",
            "data": {
                "search_type": search_type,
                "placeholder": placeholder,
                "lookup_expr": search_type,
            },
        }

    @classmethod
    def filter_json(cls, title, name, operation="has_key", allowed_keys=None, json_key=None):
        """
        Create metadata for a JSON field filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the JSON field.
            operation (str, optional): The JSON operation (has_key, contains, etc.). Defaults to "has_key".
            allowed_keys (list, optional): List of allowed keys for filtering. Defaults to None.
            json_key (str, optional): Specific JSON key to filter on. Defaults to None.

        Returns:
            dict: Metadata for the JSON filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "json",
            "data": {
                "operation": operation,
                "allowed_keys": allowed_keys,
                "key": json_key,
                "lookup_expr": operation,
            },
        }

    @classmethod
    def filter_geographic(cls, title, name, geo_type="distance", default_distance=5, distance_unit="km"):
        """
        Create metadata for a geographic filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the geographic field.
            geo_type (str, optional): The geographic operation type (distance, bbox). Defaults to "distance".
            default_distance (int, optional): Default distance value. Defaults to 5.
            distance_unit (str, optional): Distance unit (km, mi, m). Defaults to "km".

        Returns:
            dict: Metadata for the geographic filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "geographic",
            "data": {
                "geo_type": geo_type,
                "default_distance": default_distance,
                "distance_unit": distance_unit,
            },
        }

    @classmethod
    def filter_multi_field_search(cls, title, name, fields, search_type="icontains", placeholder=None):
        """
        Create metadata for a multi-field search filter.

        Args:
            title (str): The display title of the filter.
            name (str): The name of the filter.
            fields (list): List of field names to search across.
            search_type (str, optional): The search type. Defaults to "icontains".
            placeholder (str, optional): Placeholder text. Defaults to None.

        Returns:
            dict: Metadata for the multi-field search filter.
        """
        return {
            "title": title,
            "name": name,
            "type": "multi_field_search",
            "data": {
                "fields": fields,
                "search_type": search_type,
                "placeholder": placeholder,
                "lookup_expr": search_type,
            },
        }

    @classmethod
    def build_select_choices(cls, select_choices):
        """
        Build a list of choices for a select filter.

        Args:
            select_choices (Choices): A class containing the choices.
                Must be a subclass of `models.TextChoices` or `models.IntegerChoices`.

        Returns:
            list: A list of dictionaries with "title" and "value" keys.
        """
        choices = [{"title": "All", "value": "", "selected": True}]
        for choice in select_choices:
            choices.append({"title": choice.name, "value": choice.value})
        return choices

    @action(detail=False)
    def objects_filtering_data(self, request):
        """
        Return filtering metadata for the viewset.

        This action generates and returns metadata for filters and ordering
        fields defined in the viewset's [filterset_metadata](http://_vscodecontentref_/1) attribute.

        Args:
            request: The HTTP request object.

        Returns:
            Response: A JSON response containing filtering metadata.

        Raises:
            ImproperlyConfigured: If [filterset_metadata](http://_vscodecontentref_/2) is not properly configured.
        """
        filterset_metadata = getattr(self, "filterset_metadata", None)
        if not filterset_metadata:
            filterset_metadata = []

            # Populate filterset fields if filterset_metadata is empty
            filterset_fields = getattr(self, "filterset_fields", [])
            for filter_key in filterset_fields:
                filterset_metadata.append(
                    {
                        "title": filter_key.replace("_", " ").capitalize(),
                        "name": filter_key,
                        "type": "form_value",
                        "data": {"field_type": "text"},
                    }
                )

        # Add the created_at filter
        date_filter_details = self.filter_date(title=_("Creation date"), name="created_at")
        if date_filter_details not in filterset_metadata:
            filterset_metadata.append(date_filter_details)

        if not isinstance(filterset_metadata, (list, tuple)):
            raise ImproperlyConfigured(_("Wrong configuration. 'filterset_metadata' must be a dictionary."))

        filtering_data = {
            "filters": filterset_metadata,
            "ordering": getattr(self, "ordering_fields", None),
        }
        return Response(filtering_data)
