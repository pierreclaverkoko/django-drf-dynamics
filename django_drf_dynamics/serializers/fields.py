import json

from rest_framework import serializers
from django.urls import reverse_lazy


class ChoiceEnumField(serializers.SerializerMethodField):
    """
    A read-only field that gets its representation from calling a method on
    the parent serializer class or by returning a dictionary representation
    of a choice field.

    This field is useful for serializing choice fields in a structured format
    (e.g., with value, title, and CSS class).

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

    Attributes:
        NO_FIELD_PLACEHOLDER (str): Placeholder for when no method name is provided.
    """

    NO_FIELD_PLACEHOLDER = "__no_field_to_consider"

    def __init__(self, method_name=None, choice_field_name=None, **kwargs):
        """
        Initialize the ChoiceEnumField.

        Args:
            method_name (str, optional): The name of the method to call on the parent serializer.
            choice_field_name (str, optional): The name of the choice field to serialize.
            **kwargs: Additional keyword arguments for the parent class.
        """
        self.choice_field_name = choice_field_name
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

        if not self.choice_field_name:
            self.choice_field_name = field_name

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
            return self.get_choice_dict_from_value(value)

        method = getattr(self.parent, self.method_name)
        return method(value)

    def get_choice_dict_from_value(self, obj):
        """
        Get the dictionary representation of a choice field.

        Args:
            obj: The object containing the choice field.

        Returns:
            dict or any: A dictionary with value, title, and CSS class, or the raw value.
        """
        if self.choice_field_name:
            field_value = getattr(obj, self.choice_field_name, None)
            if field_value in [None, "", "None"]:
                return field_value

            field_value_display_func = getattr(obj, f"get_{self.choice_field_name}_display", None)
            field_value_css_func = getattr(obj, f"get_{self.choice_field_name}_css", None)

            if not field_value_display_func:
                return field_value

            field_value_display = field_value_display_func()
            field_value_css = field_value_css_func() if field_value_css_func else "default"

            return {"value": field_value, "title": field_value_display, "css": field_value_css}


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
