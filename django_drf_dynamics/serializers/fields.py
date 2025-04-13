import json

from rest_framework import serializers
from django.urls import reverse_lazy


class ChoiceEnumField(serializers.SerializerMethodField):
    """A read-only field that get its representation from calling a method on
    the parent serializer class. This will return a dict from the choice field
    of the same name.

    For example:

    class ExampleSerializer(Serializer):
        extra_info = ChoiceEnumField()
    """

    NO_FIELD_PLACEHOLDER = "__no_field_to_consider"

    def __init__(self, method_name=None, choice_field_name=None, **kwargs):
        self.choice_field_name = choice_field_name
        super().__init__(method_name=method_name, **kwargs)

    def bind(self, field_name, parent):
        """Bind function"""
        # We get the placeholder to send to the default
        if self.method_name is None:
            self.method_name = self.NO_FIELD_PLACEHOLDER

        # Save the field_name
        if not self.choice_field_name:
            self.choice_field_name = field_name

        super().bind(field_name, parent)

    def to_representation(self, value):
        """To representation"""
        if self.method_name == self.NO_FIELD_PLACEHOLDER:
            return self.get_choice_dict_from_value(value)

        method = getattr(self.parent, self.method_name)
        return method(value)

    def get_choice_dict_from_value(self, obj):
        """This returns the choice dictionnary from value"""
        if self.choice_field_name:
            field_value = getattr(obj, self.choice_field_name, None)
            if (field_value is None) or (not field_value) or (field_value in ["", "None"]):
                return field_value

            field_value_display_func = getattr(obj, f"get_{self.choice_field_name}_display", None)
            field_value_css_func = getattr(obj, f"get_{self.choice_field_name}_css", None)

            if not field_value_display_func:
                return field_value

            field_value_display = field_value_display_func()
            field_value_css = field_value_css_func() if field_value_css_func else "default"

            return {"value": field_value, "title": field_value_display, "css": field_value_css}


class AutocompleteRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, **kwargs):
        self.url = kwargs.pop("url", None)
        if self.url:
            self.reverse_url = reverse_lazy(self.url)
        else:
            self.reverse_url = None
        super().__init__(**kwargs)


class JsonLoadSerializerMethodField(serializers.SerializerMethodField):
    """A read-only field that get its representation from calling a method on
    the parent serializer class. This will return a (json.loads) from the field
    of the same name.

    For example:

    class ExampleSerializer(Serializer):
        extra_info = JsonLoadSerializerMethodField()
    """

    NO_FIELD_PLACEHOLDER = "__no_field_to_consider"

    def __init__(self, method_name=None, json_field_name=None, **kwargs):
        self.json_field_name = json_field_name
        super().__init__(method_name=method_name, **kwargs)

    def bind(self, field_name, parent):
        # We get the placeholder to send to the default
        if self.method_name is None:
            self.method_name = self.NO_FIELD_PLACEHOLDER

        # Save the field_name
        if not self.json_field_name:
            self.json_field_name = field_name

        super().bind(field_name, parent)

    def to_representation(self, value):
        if self.method_name == self.NO_FIELD_PLACEHOLDER:
            return self.get_json_load_from_value(value)

        method = getattr(self.parent, self.method_name)
        return method(value)

    def get_json_load_from_value(self, obj):
        if self.json_field_name:
            field_value = getattr(obj, self.json_field_name)

            if field_value is None or not field_value or field_value in ["", "None"]:
                return field_value

            return json.loads(field_value)
