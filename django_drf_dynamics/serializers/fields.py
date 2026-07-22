import json

from rest_framework import serializers
from django.urls import reverse_lazy


class ChoiceEnumField(serializers.Field):
    """
    Choice field with rich read representation and writable input.

    On read, returns ``{value, title, css}`` (via model ``get_<name>_display`` /
    ``get_<name>_css`` when available). On write, accepts a raw choice value or
    a dict with a ``value`` key.

    When ``choice_field_name`` differs from the serializer field name (e.g.
    ``status_display = ChoiceEnumField(choice_field_name="status")``), the field
    is forced read-only.

    Example usage:

    ```python
    class ExampleModel(models.Model):
        STATUS_CHOICES = [
            (1, "Active"),
            (2, "Inactive"),
        ]
        status = models.IntegerField(choices=STATUS_CHOICES)

        def get_status_css(self):
            return "success" if self.status == 1 else "danger"

    class ExampleSerializer(serializers.Serializer):
        status = ChoiceEnumField()

    # Output for an object with status=1:
    # {
    #     "status": {
    #         "value": 1,
    #         "title": "Active",
    #         "css": "success"
    #     }
    # }
    ```
    """

    NO_FIELD_PLACEHOLDER = "__no_field_to_consider"

    def __init__(self, method_name=None, choice_field_name=None, **kwargs):
        """
        Initialize the ChoiceEnumField.

        Args:
            method_name (str, optional): Custom parent serializer method for representation.
            choice_field_name (str, optional): Model choice field to serialize.
            **kwargs: Additional keyword arguments for the parent class.
        """
        self.choice_field_name = choice_field_name
        self.method_name = method_name if method_name is not None else self.NO_FIELD_PLACEHOLDER
        self._choice_map = None
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        """
        Bind the field to the parent serializer and resolve model choices.
        """
        if not self.choice_field_name:
            self.choice_field_name = field_name

        # Display aliases (different serializer name vs model field) stay read-only.
        if field_name != self.choice_field_name:
            self.read_only = True

        super().bind(field_name, parent)
        self._resolve_choices_from_model()

    def _resolve_choices_from_model(self):
        """Populate choice map from the bound ModelSerializer model when possible."""
        if self._choice_map is not None:
            return
        model = getattr(getattr(self.parent, "Meta", None), "model", None)
        if model is None or not self.choice_field_name:
            self._choice_map = {}
            return
        try:
            model_field = model._meta.get_field(self.choice_field_name)
        except Exception:
            self._choice_map = {}
            return
        raw_choices = getattr(model_field, "choices", None) or ()
        # ArrayField / similar: choices live on the base/child field.
        if not raw_choices and hasattr(model_field, "base_field"):
            raw_choices = getattr(model_field.base_field, "choices", None) or ()
        self._choice_map = {key: label for key, label in raw_choices}

    @property
    def choices(self):
        """Choice mapping for OPTIONS / dynamic forms (value -> display label)."""
        if self._choice_map is None:
            self._resolve_choices_from_model()
        return self._choice_map or {}

    def get_attribute(self, instance):
        """Return the full instance so representation can call display/css helpers."""
        return instance

    def to_representation(self, value):
        """
        Convert the instance (or value) to the rich choice representation.
        """
        if self.method_name != self.NO_FIELD_PLACEHOLDER:
            method = getattr(self.parent, self.method_name)
            return method(value)

        return self.get_choice_dict_from_value(value)

    def get_choice_dict_from_value(self, obj):
        """
        Get the dictionary representation of a choice field.

        Args:
            obj: The object containing the choice field (or None).

        Returns:
            dict | list | any: A ``{value, title, css}`` object, a list of those for
            multi-value (ArrayField) choices, or the raw value.
        """
        if obj is None:
            return None

        if not self.choice_field_name:
            return None

        field_value = getattr(obj, self.choice_field_name, None)
        if field_value in [None, "", "None"]:
            return field_value

        # Multi-value choices (e.g. ArrayField of TextChoices).
        if isinstance(field_value, (list, tuple)):
            return self._represent_multi_choice(obj, list(field_value))

        field_value_display_func = getattr(obj, f"get_{self.choice_field_name}_display", None)
        field_value_css_func = getattr(obj, f"get_{self.choice_field_name}_css", None)
        css = "default"
        if field_value_css_func:
            css_result = field_value_css_func()
            # Per-item maps belong to multi-value fields; ignore dicts for scalars.
            css = css_result if isinstance(css_result, str) else "default"

        if field_value_display_func:
            title = field_value_display_func()
        else:
            title = self.choices.get(field_value, field_value)

        if title == field_value and not field_value_css_func and not self.choices:
            return field_value

        return {"value": field_value, "title": title, "css": css}

    def _represent_multi_choice(self, obj, values):
        """Build a list of ``{value, title, css}`` for array/list choice fields."""
        css_map = {}
        field_value_css_func = getattr(obj, f"get_{self.choice_field_name}_css", None)
        if field_value_css_func:
            css_result = field_value_css_func()
            if isinstance(css_result, dict):
                css_map = css_result

        choice_map = self.choices or {}
        items = []
        for item in values:
            title = choice_map.get(item, item)
            css = css_map.get(item, "default") if css_map else "default"
            items.append({"value": item, "title": title, "css": css})
        return items

    def to_internal_value(self, data):
        """Accept a raw choice value, list of values, or ``{"value": ...}``."""
        if isinstance(data, dict):
            if "value" not in data:
                self.fail("invalid")
            data = data["value"]

        if data is None:
            if self.allow_null:
                return None
            self.fail("null")

        if isinstance(data, (list, tuple)):
            return [self._coerce_single_choice(item) for item in data]

        if isinstance(data, str) and data == "" and not self.required:
            if self.allow_null:
                return None
            return data

        return self._coerce_single_choice(data)

    def _coerce_single_choice(self, data):
        """Validate/coerce one choice value against the known choice map."""
        if isinstance(data, dict) and "value" in data:
            data = data["value"]

        choice_map = self.choices
        if choice_map:
            if data in choice_map:
                return data
            for key in choice_map:
                if str(key) == str(data):
                    return key
            self.fail("invalid_choice", input=data)
        return data

    default_error_messages = {
        "invalid": "Invalid choice payload.",
        "invalid_choice": '"{input}" is not a valid choice.',
        "null": "This field may not be null.",
    }


class AutocompleteRelatedField(serializers.PrimaryKeyRelatedField):
    """
    A custom field for handling related objects with autocomplete functionality.

    This field allows specifying a URL for retrieving related objects.

    Example usage:

    ```python
    class ExampleSerializer(serializers.Serializer):
        related_field = AutocompleteRelatedField(queryset=RelatedModel.objects.all(), url="related-model-autocomplete")
    ```

    Attributes:
        url (str): The URL for retrieving related objects.
        reverse_url (str): The resolved URL for the autocomplete endpoint.
    """

    def __init__(self, **kwargs):
        """
        Initialize the AutocompleteRelatedField.

        Args:
            **kwargs: Additional keyword arguments for the parent class.
        """
        self.url = kwargs.pop("url", None)
        if self.url:
            self.reverse_url = reverse_lazy(self.url)
        else:
            self.reverse_url = None
        super().__init__(**kwargs)


class JsonLoadSerializerMethodField(serializers.SerializerMethodField):
    """
    A read-only field that gets its representation by calling a method on
    the parent serializer or by loading JSON data from a specified field.

    Example usage:

    ```python
    class ExampleModel(models.Model):
        extra_info = models.TextField()

    class ExampleSerializer(serializers.Serializer):
        extra_info = JsonLoadSerializerMethodField()

    # Output for an object with extra_info='{"key": "value"}':
    # {
    #     "extra_info": {
    #         "key": "value"
    #     }
    # }
    ```

    Attributes:
        NO_FIELD_PLACEHOLDER (str): Placeholder for when no method name is provided.
    """

    NO_FIELD_PLACEHOLDER = "__no_field_to_consider"

    def __init__(self, method_name=None, json_field_name=None, **kwargs):
        """
        Initialize the JsonLoadSerializerMethodField.

        Args:
            method_name (str, optional): The name of the method to call on the parent serializer.
            json_field_name (str, optional): The name of the field containing JSON data.
            **kwargs: Additional keyword arguments for the parent class.
        """
        self.json_field_name = json_field_name
        super().__init__(method_name=method_name, **kwargs)

    def bind(self, field_name, parent):
        """
        Bind the field to the parent serializer.

        Args:
            field_name (str): The name of the field.
            parent (Serializer): The parent serializer instance.
        """
        if self.method_name is None:
            self.method_name = self.NO_FIELD_PLACEHOLDER

        if not self.json_field_name:
            self.json_field_name = field_name

        super().bind(field_name, parent)

    def to_representation(self, value):
        """
        Convert the field value to its serialized representation.

        Args:
            value: The field value.

        Returns:
            dict or any: The serialized representation of the field.
        """
        if self.method_name == self.NO_FIELD_PLACEHOLDER:
            return self.get_json_load_from_value(value)

        method = getattr(self.parent, self.method_name)
        return method(value)

    def get_json_load_from_value(self, obj):
        """
        Load JSON data from the specified field.

        Args:
            obj: The object containing the JSON field.

        Returns:
            dict or any: The loaded JSON data or the raw value.
        """
        if self.json_field_name:
            field_value = getattr(obj, self.json_field_name)

            if field_value in [None, "", "None"]:
                return field_value

            return json.loads(field_value)
