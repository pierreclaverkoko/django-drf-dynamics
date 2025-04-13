import logging

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ImproperlyConfigured, PermissionDenied  # noqa
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework import status as drf_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.views import APIView

from django_drf_dynamics._utils import DynamicFiltersMixin, DynamicFormsMixin
from django_drf_dynamics.serializers.defaults import ObjectsLookupSerializer

logger = logging.getLogger(__name__)


class MultipleSerializerAPIMixin:
    serializer_class = None
    detail_serializer_class = None
    create_serializer_class = None
    update_serializer_class = None
    list_serializer_class = None

    def get_serializer_class(self):
        if not hasattr(self, "action"):
            return super().get_serializer_class()

        # Handling the two names of serializers (detail and details)
        if hasattr(self, "details_serializer_class"):
            self.detail_serializer_class = self.details_serializer_class

        if self.action == "retrieve" and self.detail_serializer_class is not None:
            return self.detail_serializer_class
        elif self.action in ["update", "partial_update"] and self.update_serializer_class is not None:
            return self.update_serializer_class
        elif self.action == "create" and self.create_serializer_class is not None:
            return self.create_serializer_class
        elif self.action == "list":
            if str(self.request.query_params.get("full_object", None)).lower() == "true":
                return self.detail_serializer_class or self.list_serializer_class or self.serializer_class

            return self.list_serializer_class or self.serializer_class

        return super().get_serializer_class()


class MultiplePermissionAPIMixin:
    permission_classes = None
    detail_permission_classes = None
    create_permission_classes = None
    update_permission_classes = None
    list_permission_classes = None

    def get_permissions(self):
        if not self.permission_classes:
            self.permission_classes = []

        if not hasattr(self, "action"):
            return super().get_permissions()

        # Handling the two names of serializers (detail and details)
        if hasattr(self, "details_permission_classes"):
            self.detail_permission_classes = self.details_permission_classes

        if self.action == "retrieve" and self.detail_permission_classes is not None:
            return [permission() for permission in self.detail_permission_classes]
        elif self.action in ["update", "partial_update"] and self.update_permission_classes is not None:
            return [permission() for permission in self.update_permission_classes]
        elif self.action == "create" and self.create_permission_classes is not None:
            return [permission() for permission in self.create_permission_classes]
        elif self.action == "list" and self.list_permission_classes is not None:
            return [permission() for permission in self.list_permission_classes]
        elif self.action == "delete" and self.delete_permission_classes is not None:
            return [permission() for permission in self.delete_permission_classes]

        return super().get_permissions()


class DrfDynamicsAPIViewMixin(
    DynamicFormsMixin, DynamicFiltersMixin, MultipleSerializerAPIMixin, MultiplePermissionAPIMixin
):
    lookup_serializer_class = ObjectsLookupSerializer
    lookup_mixin_field = None

    ordering_fields = ["created_at", "id"]
    filterset_metadata = []

    def get_lookup_serializer_class(self):
        if not self.lookup_serializer_class:
            raise ImproperlyConfigured(_("'LookupModelAPIViewMixin' requires 'lookup_serializer_class' attribute"))

        return self.lookup_serializer_class

    def get_lookup_serializer(self, data, many=False):
        serializer_class = self.get_lookup_serializer_class()
        context = self.get_serializer_context()
        context["request"] = self.request
        return serializer_class(data, context=context, many=many)

    @action(detail=False)
    def objects_autocomplete(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_lookup_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_lookup_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def object_lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_data = self.request.query_params.get("lookup_data", None)

        if not self.lookup_mixin_field or not lookup_data:
            raise ImproperlyConfigured(
                _("Lookup function requires 'lookup_mixin_field' attribute and 'lookup_data' param")
            )

        lookup_data_validated, lookup_data, lookup_data_invalid_message = self.validate_lookup_data(lookup_data)
        if not lookup_data_validated:
            return Response(
                {"error": lookup_data_invalid_message or _("Could not validate the lookup data.")},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        lookup_filter = Q()

        if isinstance(self.lookup_mixin_field, list):
            for lf in self.lookup_mixin_field:
                field_lookup_filter = Q()  # init
                # We check queryset functions
                if hasattr(queryset.model, f"lookup_{lf}_filter"):
                    queryset_func = getattr(queryset.model, f"lookup_{lf}_filter", queryset)
                    queryset_qu = queryset_func(lookup_data=lookup_data)
                    if queryset_qu:
                        field_lookup_filter = lookup_filter | queryset_qu
                else:
                    field_lookup_filter = lookup_filter | Q(**{lf: lookup_data})

                try:
                    # We test queryset here
                    queryset.filter(field_lookup_filter)
                    lookup_filter = field_lookup_filter  # We update the main lookup filter
                except ValueError:
                    logger.debug(f"Lookup error for '{queryset.model}' with field '{lf}' and data '{lookup_data}'")
        else:
            try:
                lookup_filter = Q(**{self.lookup_mixin_field: lookup_data})
            except ValueError:
                logger.debug(
                    f"Lookup error for '{queryset.model}' with field '{self.lookup_mixin_field}' and data '{lookup_data}'"
                )

        queryset = queryset.filter(lookup_filter)

        if queryset.count() > 1:
            logger.debug(f"LOOKUP MULTIPLE ERROR :: {queryset}")
            raise NotFound(_("Lookup received more than one object."))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_lookup_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_lookup_serializer(queryset, many=True)

        return Response(serializer.data)

    def validate_lookup_data(self, value: str | int) -> (bool, str | int, str):
        """Override this to validate lookup data.

        This will raise
        """
        message = _("Lookup data validated")
        try:
            if isinstance(value, (str, int)):
                value = int(value)
        except Exception as err:
            logger.error(f"ERROR {err}")
        return True, value, message


class ListOverviewAPIViewMixin(MultipleSerializerAPIMixin):
    OVERVIEW_LIST_LENGTH = 4

    class OverviewType:
        class Data:
            DEFAULT_CURRENCY_CODE = "BIF"

            TAG_PRIMARY, TAG_INFO, TAG_SECONDARY, TAG_WARNING, TAG_SUCCESS, TAG_DANGER = (
                "primary",
                "info",
                "secondary",
                "warning",
                "success",
                "danger",
            )

        NUMBER = "number"
        FILE_SIZE = "filesize"
        AMOUNT = "amount"
        TEXT = "text"
        TAG = "tag"

    @action(detail=False)
    def objects_overview(self, request):
        overview_list = self.get_objects_overview_data()

        if not isinstance(overview_list, list):
            raise RuntimeError("Overview data from function 'get_objects_overview_data' must be instance of list.")

        if len(overview_list) > self.OVERVIEW_LIST_LENGTH:
            raise RuntimeError("Overview data length max is 4.")

        return Response(overview_list)

    def get_objects_overview_data(self):
        raise NotImplementedError("Overview sub views must define the method 'get_objects_overview_data'.")


class CustomGenericViewset(ListOverviewAPIViewMixin, DrfDynamicsAPIViewMixin, viewsets.GenericViewSet):
    pass
