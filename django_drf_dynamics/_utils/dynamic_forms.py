from django.utils.translation import gettext as _
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import ValidationError, Serializer
from rest_framework.utils.serializer_helpers import ReturnDict  # BindingDict,

from django_drf_dynamics.serializers.fields import AutocompleteRelatedField


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
        "imagefield": "file",
        "relationfield": "select",
        "relatedfield": "select",
        "autocompletefield": "autocomplete",
        "primarykeyrelatedfield": "autocomplete",
        "jsonfield": "json",
        "listfield": "array",
        "dictfield": "object",
        "nestedserializerfield": "object",
        "nestedlistserializerfield": "array",
        "nesteddictserializerfield": "object",
    }

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
            field_data = {
                "type": field_type,
                "html_type": self.SERIALIZER_FIELD_MAPPING.get(field_type, field_type),
                "label": field.label or (field_name.lower().replace("_", " ").capitalize()),
                "required": field.required or getattr(field, "allow_null", False),
                "help_text": field.help_text,
                "choices": (
                    field.choices
                    if not isinstance(field, AutocompleteRelatedField) and hasattr(field, "choices")
                    else None
                ),
                "value": (serializer.data.get(field_name, None) if isinstance(serializer.data, ReturnDict) else None),
                "accept_multiple_entries": False,
            }

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
