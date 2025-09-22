import logging
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from .list_backends import DjangoOrmListBackend, ElasticsearchListBackend, WebSocketListBackend

logger = logging.getLogger(__name__)


class ListConfigurationMixin:
    """
    A mixin to provide list configuration capabilities.

    This mixin allows views to define list configurations that can be used
    to create lightweight, customizable list components for frontend consumption.

    Example usage:

    ```python
    class ProductViewSet(ListConfigurationMixin, viewsets.ModelViewSet):
        queryset = Product.objects.all()
        list_configurations = {
            'compact': {
                'fields': ['id', 'name', 'price'],
                'per_page': 20,
                'enable_search': True,
                'search_fields': ['name', 'description'],
                'enable_filters': True,
                'enable_sorting': True,
                'sorting_fields': ['name', 'price', 'created_at'],
            },
            'detailed': {
                'fields': ['id', 'name', 'price', 'description', 'category', 'created_at'],
                'per_page': 10,
                'enable_search': True,
                'search_fields': ['name', 'description', 'category__name'],
                'enable_filters': True,
                'enable_sorting': True,
                'sorting_fields': ['name', 'price', 'created_at', 'category__name'],
            }
        }
    ```
    """

    list_configurations = {}
    default_list_configuration = "default"

    def get_list_configuration(self, config_name: str = None) -> Dict[str, Any]:
        """
        Get a specific list configuration.

        Args:
            config_name (str, optional): Name of the configuration. Defaults to None.

        Returns:
            Dict[str, Any]: The list configuration dictionary

        Raises:
            ValidationError: If the configuration doesn't exist
        """
        config_name = config_name or self.default_list_configuration

        if config_name not in self.list_configurations:
            # Generate default configuration if none exists
            if not self.list_configurations:
                return self._generate_default_list_configuration()
            raise ValidationError(_(f"List configuration '{config_name}' not found"))

        return self.list_configurations[config_name]

    def _generate_default_list_configuration(self) -> Dict[str, Any]:
        """
        Generate a default list configuration based on the serializer.

        Returns:
            Dict[str, Any]: Default list configuration
        """
        serializer = self.get_serializer()
        fields = list(serializer.fields.keys())[:10]  # Limit to first 10 fields

        return {
            "fields": fields,
            "per_page": 25,
            "enable_search": False,
            "search_fields": [],
            "enable_filters": hasattr(self, "filterset_metadata"),
            "enable_sorting": True,
            "sorting_fields": getattr(self, "ordering_fields", ["id"]),
        }

    @action(detail=False, methods=["get"])
    def list_configurations_metadata(self, request):
        """
        Return available list configurations for this view.

        Returns:
            Response: List of available configurations with their metadata
        """
        configurations = {}

        for config_name, config in self.list_configurations.items():
            configurations[config_name] = {
                "name": config_name,
                "title": config.get("title", config_name.replace("_", " ").title()),
                "description": config.get("description", ""),
                "fields_count": len(config.get("fields", [])),
                "per_page": config.get("per_page", 25),
                "has_search": config.get("enable_search", False),
                "has_filters": config.get("enable_filters", False),
                "has_sorting": config.get("enable_sorting", False),
            }

        return Response(configurations)


class DynamicListMixin(ListConfigurationMixin):
    """
    A mixin to provide dynamic list functionality with multiple backends.

    This mixin combines list configuration with dynamic backends to create
    flexible, lightweight list components that work with Django ORM,
    Elasticsearch DSL, and WebSocket connections.

    Example usage:

    ```python
    class ProductViewSet(DynamicListMixin, viewsets.ModelViewSet):
        queryset = Product.objects.all()
        list_backend = 'django_orm'  # or 'elasticsearch', 'websocket'
        enable_list_caching = True
        list_cache_timeout = 300  # 5 minutes
    ```
    """

    list_backend = "django_orm"
    enable_list_caching = False
    list_cache_timeout = 300  # 5 minutes
    list_cache_key_prefix = "dynamic_list"

    # Backend configuration
    list_backends = {
        "django_orm": DjangoOrmListBackend,
        "elasticsearch": ElasticsearchListBackend,
        "websocket": WebSocketListBackend,
    }

    def get_list_backend(self):
        """
        Get the configured list backend instance.

        Returns:
            BaseListBackend: The list backend instance

        Raises:
            ImproperlyConfigured: If backend is not found
        """
        backend_class = self.list_backends.get(self.list_backend)

        if not backend_class:
            raise ImproperlyConfigured(f"List backend '{self.list_backend}' not found")

        return backend_class()

    def get_list_cache_key(self, config_name: str, **kwargs) -> str:
        """
        Generate a cache key for list data.

        Args:
            config_name (str): The configuration name
            **kwargs: Additional parameters for the cache key

        Returns:
            str: The cache key
        """
        model_name = self.queryset.model._meta.label_lower
        user_id = (
            self.request.user.id if hasattr(self.request, "user") and self.request.user.is_authenticated else "anon"
        )
        params_hash = hash(str(sorted(kwargs.items())))

        return f"{self.list_cache_key_prefix}:{model_name}:{config_name}:{user_id}:{params_hash}"

    def get_cached_list_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached list data.

        Args:
            cache_key (str): The cache key

        Returns:
            Optional[Dict[str, Any]]: Cached data or None
        """
        if not self.enable_list_caching:
            return None

        return cache.get(cache_key)

    def set_cached_list_data(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Store list data in cache.

        Args:
            cache_key (str): The cache key
            data (Dict[str, Any]): The data to cache
        """
        if self.enable_list_caching:
            cache.set(cache_key, data, timeout=self.list_cache_timeout)

    @action(detail=False, methods=["get"])
    def dynamic_list(self, request):
        """
        Return a dynamic list based on the specified configuration.

        Query parameters:
        - config: Configuration name (default: 'default')
        - page: Page number (default: 1)
        - per_page: Items per page (overrides config setting)
        - search: Search term
        - ordering: Ordering field
        - Any filter parameters defined in filterset_metadata

        Returns:
            Response: Paginated list data with metadata
        """
        config_name = request.query_params.get("config", self.default_list_configuration)
        page = int(request.query_params.get("page", 1))
        search = request.query_params.get("search", "")
        ordering = request.query_params.get("ordering", "")

        try:
            config = self.get_list_configuration(config_name)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Override per_page from query params if provided
        per_page = int(request.query_params.get("per_page", config.get("per_page", 25)))

        # Generate cache key
        cache_params = {
            "page": page,
            "per_page": per_page,
            "search": search,
            "ordering": ordering,
            "filters": dict(request.query_params.items()),
        }
        cache_key = self.get_list_cache_key(config_name, **cache_params)

        # Check cache first
        cached_data = self.get_cached_list_data(cache_key)
        if cached_data:
            return Response(cached_data)

        # Get backend and process list
        backend = self.get_list_backend()

        try:
            list_data = backend.get_list_data(
                view=self,
                request=request,
                config=config,
                page=page,
                per_page=per_page,
                search=search,
                ordering=ordering,
            )

            # Cache the result
            self.set_cached_list_data(cache_key, list_data)

            return Response(list_data)

        except Exception as e:
            logger.error(f"Error processing dynamic list: {e}")
            return Response({"error": _("Error processing list data")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"])
    def list_metadata(self, request):
        """
        Return metadata for list configuration.

        Query parameters:
        - config: Configuration name

        Returns:
            Response: List metadata including fields, filters, sorting options
        """
        config_name = request.query_params.get("config", self.default_list_configuration)

        try:
            config = self.get_list_configuration(config_name)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        metadata = {
            "config_name": config_name,
            "fields": self._get_field_metadata(config.get("fields", [])),
            "pagination": {
                "per_page": config.get("per_page", 25),
                "per_page_options": config.get("per_page_options", [10, 25, 50, 100]),
            },
            "search": {
                "enabled": config.get("enable_search", False),
                "fields": config.get("search_fields", []),
                "placeholder": config.get("search_placeholder", _("Search...")),
            },
            "sorting": {
                "enabled": config.get("enable_sorting", False),
                "fields": self._get_sorting_metadata(config.get("sorting_fields", [])),
                "default": config.get("default_ordering", ""),
            },
            "filters": {
                "enabled": config.get("enable_filters", False),
                "fields": getattr(self, "filterset_metadata", []),
            },
        }

        return Response(metadata)

    def _get_field_metadata(self, field_names: List[str]) -> List[Dict[str, Any]]:
        """
        Get metadata for list fields.

        Args:
            field_names (List[str]): List of field names

        Returns:
            List[Dict[str, Any]]: Field metadata
        """
        serializer = self.get_serializer()
        field_metadata = []

        for field_name in field_names:
            if field_name in serializer.fields:
                field = serializer.fields[field_name]
                field_metadata.append(
                    {
                        "name": field_name,
                        "label": field.label or field_name.replace("_", " ").title(),
                        "type": field.__class__.__name__.lower(),
                        "required": field.required,
                        "read_only": field.read_only,
                        "help_text": field.help_text or "",
                    }
                )
            else:
                # Handle nested fields or custom fields
                field_metadata.append(
                    {
                        "name": field_name,
                        "label": field_name.replace("_", " ").title(),
                        "type": "unknown",
                        "required": False,
                        "read_only": True,
                        "help_text": "",
                    }
                )

        return field_metadata

    def _get_sorting_metadata(self, sorting_fields: List[str]) -> List[Dict[str, Any]]:
        """
        Get metadata for sorting fields.

        Args:
            sorting_fields (List[str]): List of sorting field names

        Returns:
            List[Dict[str, Any]]: Sorting metadata
        """
        sorting_metadata = []

        for field_name in sorting_fields:
            sorting_metadata.append(
                {
                    "name": field_name,
                    "label": field_name.replace("_", " ").title(),
                    "asc": field_name,
                    "desc": f"-{field_name}",
                }
            )

        return sorting_metadata


class RealtimeListMixin(DynamicListMixin):
    """
    A mixin to provide real-time list updates via WebSocket connections.

    This mixin extends DynamicListMixin with real-time capabilities,
    allowing lists to be updated in real-time as data changes.

    Example usage:

    ```python
    class ProductViewSet(RealtimeListMixin, viewsets.ModelViewSet):
        queryset = Product.objects.all()
        realtime_group_name = 'products'
        realtime_events = ['create', 'update', 'delete']

        def get_realtime_group_name(self, config_name):
            return f"{self.realtime_group_name}_{config_name}"
    ```

    Requires channels for WebSocket support.
    """

    realtime_group_name = None
    realtime_events = ["create", "update", "delete"]
    enable_realtime = True

    def get_realtime_group_name(self, config_name: str = None) -> str:
        """
        Get the WebSocket group name for real-time updates.

        Args:
            config_name (str, optional): Configuration name. Defaults to None.

        Returns:
            str: WebSocket group name
        """
        base_name = self.realtime_group_name or self.queryset.model._meta.label_lower
        if config_name:
            return f"{base_name}_{config_name}"
        return base_name

    @action(detail=False, methods=["post"])
    def subscribe_realtime_updates(self, request):
        """
        Subscribe to real-time list updates.

        Request body:
        - config: Configuration name
        - events: List of events to subscribe to

        Returns:
            Response: Subscription details
        """
        if not self.enable_realtime:
            return Response({"error": _("Real-time updates are not enabled")}, status=status.HTTP_400_BAD_REQUEST)

        config_name = request.data.get("config", self.default_list_configuration)
        events = request.data.get("events", self.realtime_events)

        try:
            # Validate configuration
            self.get_list_configuration(config_name)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        group_name = self.get_realtime_group_name(config_name)

        subscription_data = {
            "group_name": group_name,
            "config_name": config_name,
            "events": events,
            "websocket_url": f"/ws/lists/{group_name}/",
            "instructions": {
                "connect": f"Connect to WebSocket at: /ws/lists/{group_name}/",
                "message_format": {
                    "type": "Event type (create, update, delete)",
                    "data": "Updated object data",
                    "config": "Configuration name",
                    "timestamp": "Event timestamp",
                },
            },
        }

        return Response(subscription_data)

    def send_realtime_update(self, event_type: str, instance: Any, config_name: str = None):
        """
        Send real-time update to WebSocket subscribers.

        Args:
            event_type (str): Type of event (create, update, delete)
            instance (Any): The model instance
            config_name (str, optional): Configuration name. Defaults to None.
        """
        if not self.enable_realtime or event_type not in self.realtime_events:
            return

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
        except ImportError:
            logger.warning("Channels not installed. Real-time updates unavailable.")
            return

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = self.get_realtime_group_name(config_name)

        # Serialize the instance
        serializer = self.get_serializer(instance)

        message = {
            "type": "list_update",
            "event_type": event_type,
            "data": serializer.data,
            "config": config_name,
            "timestamp": timezone.now().isoformat(),
        }

        async_to_sync(channel_layer.group_send)(group_name, message)

    def perform_create(self, serializer):
        """Override to send real-time updates on create."""
        instance = serializer.save()
        self.send_realtime_update("create", instance)
        return instance

    def perform_update(self, serializer):
        """Override to send real-time updates on update."""
        instance = serializer.save()
        self.send_realtime_update("update", instance)
        return instance

    def perform_destroy(self, instance):
        """Override to send real-time updates on delete."""
        self.send_realtime_update("delete", instance)
        instance.delete()
