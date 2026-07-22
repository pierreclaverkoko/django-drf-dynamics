from django.utils.translation import gettext as _
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.fields import ChoiceField
from rest_framework.serializers import ValidationError, Serializer
from rest_framework.utils.serializer_helpers import ReturnDict  # BindingDict,

from django_drf_dynamics.serializers.fields import AutocompleteRelatedField, ChoiceEnumField


class DynamicFormsMixin:
    """
    A mixin to dynamically generate JSON form fields based on serializer definitions.

    This mixin provides methods to extract field information from serializers
    and return it in a format suitable for building dynamic forms. It supports
    nested serializers, autocomplete fields, and additional metadata like
    help text, choices, and validation constraints.

    Example usage:

    ```python
    class ExampleViewSet(viewsets.ModelViewSet, DynamicFormsMixin):
        queryset = ExampleModel.objects.all()
        serializer_class = ExampleSerializer

        @action(detail=False)
        def object_dynamic_form(self, request):
            return super().object_dynamic_form(request)
    ```
    """

    SERIALIZER_FIELD_MAPPING = {
        "charfield": "text",
        "decimalfield": "number",
        "integerfield": "number",
        "booleanfield": "checkbox",
        "emailfield": "email",
        "urlfield": "url",
        "datetimefield": "datetime",
        "datefield": "date",
        "timefield": "time",
        "choicefield": "select",
        "multiplechoicefield": "select-multiple",
        "filefield": "file",
        "imagefield": "image",
        "relationfield": "select",
        "relatedfield": "select",
        "autocompletefield": "autocomplete",
        "primarykeyrelatedfield": "autocomplete",
        "jsonfield": "json",
        "choiceenumfield": "select",
        "listfield": "array",
        "dictfield": "object",
        "nestedserializerfield": "object",
        "nestedlistserializerfield": "array",
        "nesteddictserializerfield": "object",
    }


    def _get_form_field_choices(self, field):
        """
        Return choices for dynamic forms without triggering related-field querysets.

        ChoiceEnumField and ChoiceField expose a mapping; normalize to a list of
        ``{"value", "display_name"}`` dicts for frontend select widgets.
        """
        if isinstance(field, AutocompleteRelatedField):
            return None
        # Related fields expose a ``choices`` property that queries the DB.
        if getattr(field, "queryset", None) is not None or hasattr(field, "get_queryset"):
            return None
        if isinstance(field, ChoiceEnumField):
            choice_map = field.choices or {}
            return [{"value": value, "display_name": str(label)} for value, label in choice_map.items()]
        choice_map = getattr(field, "_choices", None)
        if choice_map is None and "choices" in getattr(field, "__dict__", {}):
            choice_map = field.__dict__.get("choices")
        if choice_map is None:
            # Prefer typed ChoiceField-style fields only (avoid descriptor side effects).
            if isinstance(field, ChoiceField):
                choice_map = field.choices
        if not choice_map:
            return None
        if isinstance(choice_map, dict):
            return [{"value": value, "display_name": str(label)} for value, label in choice_map.items()]
        if isinstance(choice_map, (list, tuple)):
            normalized = []
            for item in choice_map:
                if isinstance(item, dict) and "value" in item:
                    normalized.append(
                        {
                            "value": item["value"],
                            "display_name": str(item.get("display_name", item.get("label", item["value"]))),
                        }
                    )
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    normalized.append({"value": item[0], "display_name": str(item[1])})
            return normalized or None
        return None

    def get_dynamic_form_fields(self, serializer):
        """
        Extract field information from a serializer and create a dictionary
        suitable for building dynamic JSON form fields.

        Args:
            serializer (Serializer): The serializer instance to extract fields from.

        Returns:
            dict: A dictionary containing field metadata for dynamic form generation.
        """
        # serializer_fields = (
        #     {**serializer._declared_fields, **serializer.fields}
        #     if isinstance(serializer.fields, BindingDict)
        #     else serializer._declared_fields
        # )

        try:
            serializer_fields = serializer().fields
            serializer = serializer()
        except TypeError:
            serializer_fields = serializer.fields

        form_fields = {}
        for field_name, field in serializer_fields.items():
            if field.read_only:
                continue

            field_type = field.__class__.__name__.lower()  # Convert class name to lowercase type
            html_type = self.SERIALIZER_FIELD_MAPPING.get(field_type, field_type)
            field_data = {
                "type": field_type,
                "html_type": html_type,
                "label": field.label or (field_name.lower().replace("_", " ").capitalize()),
                "required": bool(field.required),
                "help_text": field.help_text,
                "choices": self._get_form_field_choices(field),
                "value": (serializer.data.get(field_name, None) if isinstance(serializer.data, ReturnDict) else None),
                "accept_multiple_entries": False,
            }

            if html_type == "json" or field_type in {"jsonfield", "dictfield"}:
                field_data["editor"] = "key_value_json"

            if isinstance(field, ChoiceEnumField):
                field_data["type"] = "choiceenumfield"
                field_data["html_type"] = "select"

            if isinstance(field, AutocompleteRelatedField):
                field_data.update(
                    {
                        "type": "autocomplete",
                        "url": field.reverse_url or None,
                        # "value": serializer.data.get("id", None),
                    }
                )

            if getattr(field, "max_length", None):
                field_data["max_length"] = field.max_length

            if getattr(field, "max_digits", None):
                field_data["max_digits"] = field.max_digits

            if getattr(field, "decimal_places", None):
                field_data["decimal_places"] = field.decimal_places

            # File / image upload metadata for frontend dropzone editors
            if field_type in {"filefield", "imagefield"} or html_type in {"file", "image"}:
                field_data["accept"] = "image/*" if (field_type == "imagefield" or html_type == "image") else "*/*"

            # ListField of files/images → multi upload
            child = getattr(field, "child", None)
            if field_type == "listfield" and child is not None:
                child_type = child.__class__.__name__.lower()
                if child_type in {"filefield", "imagefield"}:
                    field_data["accept_multiple_entries"] = True
                    field_data["html_type"] = "image" if child_type == "imagefield" else "file"
                    field_data["type"] = child_type
                    field_data["accept"] = "image/*" if child_type == "imagefield" else "*/*"

            # MULTIPLE FIELDS MANAGEMENT
            if isinstance(field, Serializer):
                field_data["fields"] = self.get_dynamic_form_fields(field)
                field_data["type"] = "serializerfield"
                field_data["html_type"] = "object"

                # MANY MANAGEMENT
                if hasattr(field, "many") and field.many:
                    field_data["accept_multiple_entries"] = True

                # CHILDREN MANAGEMENT
                if hasattr(field, "child") and field.child:
                    field_data["fields"] = self.get_dynamic_form_fields(field.child)
                elif hasattr(field, "child_relation") and field.child_relation:
                    field_data["fields"] = self.get_dynamic_form_fields(field.child_relation)
            elif isinstance(field, list):
                field_data["fields"] = [
                    self.get_dynamic_form_fields(item) if isinstance(item, Serializer) else item for item in field
                ]
            elif isinstance(field, dict):
                field_data["fields"] = {
                    key: self.get_dynamic_form_fields(value) if isinstance(value, Serializer) else value
                    for key, value in field.items()
                }

            form_fields[field_name] = field_data

        return form_fields

    @action(detail=False)
    def object_dynamic_form(self, request):
        """
        Generate a dynamic JSON form based on the selected serializer.

        This method returns a JSON representation of a form based on the
        serializer specified by the `form_name` query parameter. If no
        `form_name` is provided, the default serializer is used.

        Args:
            request: The HTTP request object.

        Returns:
            Response: A JSON response containing the form fields.

        Raises:
            ValidationError: If the specified `form_name` is invalid.
        """
        form_name = self.request.query_params.get("form_name", None)
        serializer_name = "serializer_class"
        if form_name:
            serializer_name = f"{form_name}_{serializer_name}"

        if hasattr(self, serializer_name):
            form_data = self.get_dynamic_form_fields(getattr(self, serializer_name, self.serializer_class))
            return Response(form_data)
        else:
            raise ValidationError(_("Invalid form name"))

    @action(detail=True)
    def single_object_dynamic_form(self, request, pk=None):
        """
        Generate a dynamic JSON form for a single object based on the selected serializer.

        This method returns a JSON representation of a form for a specific object
        identified by its primary key (`pk`). The serializer is determined by the
        `form_name` query parameter or defaults to the view's serializer.

        Args:
            request: The HTTP request object.
            pk: The primary key of the object.

        Returns:
            Response: A JSON response containing the form fields.
        """
        form_name = self.request.query_params.get("form_name", None)
        serializer_name = "serializer_class"
        if form_name:
            serializer_name = f"{form_name}_{serializer_name}"

        if hasattr(self, serializer_name):
            dynamic_serializer_class = getattr(self, serializer_name, self.serializer_class)

            object_ = self.get_object()
            serializer = dynamic_serializer_class(object_)
            form_data = self.get_dynamic_form_fields(serializer)
            return Response(form_data)
