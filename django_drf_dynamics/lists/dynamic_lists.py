import logging
from typing import Any, Dict, List, Optional, Union

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
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
    default_list_configuration = 'default'
    
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
            'fields': fields,
            'per_page': 25,
            'enable_search': False,
            'search_fields': [],
            'enable_filters': hasattr(self, 'filterset_metadata'),
            'enable_sorting': True,
            'sorting_fields': getattr(self, 'ordering_fields', ['id']),
        }
    
    @action(detail=False, methods=['get'])
    def list_configurations_metadata(self, request):
        """
        Return available list configurations for this view.
        
        Returns:
            Response: List of available configurations with their metadata
        """
        configurations = {}
        
        for config_name, config in self.list_configurations.items():
            configurations[config_name] = {
                'name': config_name,
                'title': config.get('title', config_name.replace('_', ' ').title()),
                'description': config.get('description', ''),
                'fields_count': len(config.get('fields', [])),
                'per_page': config.get('per_page', 25),
                'has_search': config.get('enable_search', False),
                'has_filters': config.get('enable_filters', False),
                'has_sorting': config.get('enable_sorting', False),
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
    
    list_backend = 'django_orm'
    enable_list_caching = False
    list_cache_timeout = 300  # 5 minutes
    list_cache_key_prefix = 'dynamic_list'
    
    # Backend configuration
    list_backends = {
        'django_orm': DjangoOrmListBackend,
        'elasticsearch': ElasticsearchListBackend,
        'websocket': WebSocketListBackend,
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
    
    def get_list_cache_key(self, config_name: str, **kwargs) -> str:\n        \"\"\"\n        Generate a cache key for list data.\n        \n        Args:\n            config_name (str): The configuration name\n            **kwargs: Additional parameters for the cache key\n            \n        Returns:\n            str: The cache key\n        \"\"\"\n        model_name = self.queryset.model._meta.label_lower\n        user_id = self.request.user.id if hasattr(self.request, 'user') and self.request.user.is_authenticated else 'anon'\n        params_hash = hash(str(sorted(kwargs.items())))\n        \n        return f\"{self.list_cache_key_prefix}:{model_name}:{config_name}:{user_id}:{params_hash}\"\n    \n    def get_cached_list_data(self, cache_key: str) -> Optional[Dict[str, Any]]:\n        \"\"\"\n        Retrieve cached list data.\n        \n        Args:\n            cache_key (str): The cache key\n            \n        Returns:\n            Optional[Dict[str, Any]]: Cached data or None\n        \"\"\"\n        if not self.enable_list_caching:\n            return None\n        \n        return cache.get(cache_key)\n    \n    def set_cached_list_data(self, cache_key: str, data: Dict[str, Any]) -> None:\n        \"\"\"\n        Store list data in cache.\n        \n        Args:\n            cache_key (str): The cache key\n            data (Dict[str, Any]): The data to cache\n        \"\"\"\n        if self.enable_list_caching:\n            cache.set(cache_key, data, timeout=self.list_cache_timeout)\n    \n    @action(detail=False, methods=['get'])\n    def dynamic_list(self, request):\n        \"\"\"\n        Return a dynamic list based on the specified configuration.\n        \n        Query parameters:\n        - config: Configuration name (default: 'default')\n        - page: Page number (default: 1)\n        - per_page: Items per page (overrides config setting)\n        - search: Search term\n        - ordering: Ordering field\n        - Any filter parameters defined in filterset_metadata\n        \n        Returns:\n            Response: Paginated list data with metadata\n        \"\"\"\n        config_name = request.query_params.get('config', self.default_list_configuration)\n        page = int(request.query_params.get('page', 1))\n        search = request.query_params.get('search', '')\n        ordering = request.query_params.get('ordering', '')\n        \n        try:\n            config = self.get_list_configuration(config_name)\n        except ValidationError as e:\n            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)\n        \n        # Override per_page from query params if provided\n        per_page = int(request.query_params.get('per_page', config.get('per_page', 25)))\n        \n        # Generate cache key\n        cache_params = {\n            'page': page,\n            'per_page': per_page,\n            'search': search,\n            'ordering': ordering,\n            'filters': dict(request.query_params.items())\n        }\n        cache_key = self.get_list_cache_key(config_name, **cache_params)\n        \n        # Check cache first\n        cached_data = self.get_cached_list_data(cache_key)\n        if cached_data:\n            return Response(cached_data)\n        \n        # Get backend and process list\n        backend = self.get_list_backend()\n        \n        try:\n            list_data = backend.get_list_data(\n                view=self,\n                request=request,\n                config=config,\n                page=page,\n                per_page=per_page,\n                search=search,\n                ordering=ordering\n            )\n            \n            # Cache the result\n            self.set_cached_list_data(cache_key, list_data)\n            \n            return Response(list_data)\n            \n        except Exception as e:\n            logger.error(f\"Error processing dynamic list: {e}\")\n            return Response(\n                {'error': _('Error processing list data')},\n                status=status.HTTP_500_INTERNAL_SERVER_ERROR\n            )\n    \n    @action(detail=False, methods=['get'])\n    def list_metadata(self, request):\n        \"\"\"\n        Return metadata for list configuration.\n        \n        Query parameters:\n        - config: Configuration name\n        \n        Returns:\n            Response: List metadata including fields, filters, sorting options\n        \"\"\"\n        config_name = request.query_params.get('config', self.default_list_configuration)\n        \n        try:\n            config = self.get_list_configuration(config_name)\n        except ValidationError as e:\n            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)\n        \n        metadata = {\n            'config_name': config_name,\n            'fields': self._get_field_metadata(config.get('fields', [])),\n            'pagination': {\n                'per_page': config.get('per_page', 25),\n                'per_page_options': config.get('per_page_options', [10, 25, 50, 100])\n            },\n            'search': {\n                'enabled': config.get('enable_search', False),\n                'fields': config.get('search_fields', []),\n                'placeholder': config.get('search_placeholder', _('Search...'))\n            },\n            'sorting': {\n                'enabled': config.get('enable_sorting', False),\n                'fields': self._get_sorting_metadata(config.get('sorting_fields', [])),\n                'default': config.get('default_ordering', '')\n            },\n            'filters': {\n                'enabled': config.get('enable_filters', False),\n                'fields': getattr(self, 'filterset_metadata', [])\n            }\n        }\n        \n        return Response(metadata)\n    \n    def _get_field_metadata(self, field_names: List[str]) -> List[Dict[str, Any]]:\n        \"\"\"\n        Get metadata for list fields.\n        \n        Args:\n            field_names (List[str]): List of field names\n            \n        Returns:\n            List[Dict[str, Any]]: Field metadata\n        \"\"\"\n        serializer = self.get_serializer()\n        field_metadata = []\n        \n        for field_name in field_names:\n            if field_name in serializer.fields:\n                field = serializer.fields[field_name]\n                field_metadata.append({\n                    'name': field_name,\n                    'label': field.label or field_name.replace('_', ' ').title(),\n                    'type': field.__class__.__name__.lower(),\n                    'required': field.required,\n                    'read_only': field.read_only,\n                    'help_text': field.help_text or ''\n                })\n            else:\n                # Handle nested fields or custom fields\n                field_metadata.append({\n                    'name': field_name,\n                    'label': field_name.replace('_', ' ').title(),\n                    'type': 'unknown',\n                    'required': False,\n                    'read_only': True,\n                    'help_text': ''\n                })\n        \n        return field_metadata\n    \n    def _get_sorting_metadata(self, sorting_fields: List[str]) -> List[Dict[str, Any]]:\n        \"\"\"\n        Get metadata for sorting fields.\n        \n        Args:\n            sorting_fields (List[str]): List of sorting field names\n            \n        Returns:\n            List[Dict[str, Any]]: Sorting metadata\n        \"\"\"\n        sorting_metadata = []\n        \n        for field_name in sorting_fields:\n            sorting_metadata.append({\n                'name': field_name,\n                'label': field_name.replace('_', ' ').title(),\n                'asc': field_name,\n                'desc': f'-{field_name}'\n            })\n        \n        return sorting_metadata


class RealtimeListMixin(DynamicListMixin):
    """
    A mixin to provide real-time list updates via WebSocket connections.
    
    This mixin extends DynamicListMixin with real-time capabilities,
    allowing lists to be updated in real-time as data changes.
    
    Example usage:
    
    ```python\n    class ProductViewSet(RealtimeListMixin, viewsets.ModelViewSet):\n        queryset = Product.objects.all()\n        realtime_group_name = 'products'\n        realtime_events = ['create', 'update', 'delete']\n        \n        def get_realtime_group_name(self, config_name):\n            return f\"{self.realtime_group_name}_{config_name}\"\n    ```\n    \n    Requires channels for WebSocket support.\n    \"\"\"\n    \n    realtime_group_name = None\n    realtime_events = ['create', 'update', 'delete']\n    enable_realtime = True\n    \n    def get_realtime_group_name(self, config_name: str = None) -> str:\n        \"\"\"\n        Get the WebSocket group name for real-time updates.\n        \n        Args:\n            config_name (str, optional): Configuration name. Defaults to None.\n            \n        Returns:\n            str: WebSocket group name\n        \"\"\"\n        base_name = self.realtime_group_name or self.queryset.model._meta.label_lower\n        if config_name:\n            return f\"{base_name}_{config_name}\"\n        return base_name\n    \n    @action(detail=False, methods=['post'])\n    def subscribe_realtime_updates(self, request):\n        \"\"\"\n        Subscribe to real-time list updates.\n        \n        Request body:\n        - config: Configuration name\n        - events: List of events to subscribe to\n        \n        Returns:\n            Response: Subscription details\n        \"\"\"\n        if not self.enable_realtime:\n            return Response(\n                {'error': _('Real-time updates are not enabled')},\n                status=status.HTTP_400_BAD_REQUEST\n            )\n        \n        config_name = request.data.get('config', self.default_list_configuration)\n        events = request.data.get('events', self.realtime_events)\n        \n        try:\n            # Validate configuration\n            self.get_list_configuration(config_name)\n        except ValidationError as e:\n            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)\n        \n        group_name = self.get_realtime_group_name(config_name)\n        \n        subscription_data = {\n            'group_name': group_name,\n            'config_name': config_name,\n            'events': events,\n            'websocket_url': f'/ws/lists/{group_name}/',\n            'instructions': {\n                'connect': f'Connect to WebSocket at: /ws/lists/{group_name}/',\n                'message_format': {\n                    'type': 'Event type (create, update, delete)',\n                    'data': 'Updated object data',\n                    'config': 'Configuration name',\n                    'timestamp': 'Event timestamp'\n                }\n            }\n        }\n        \n        return Response(subscription_data)\n    \n    def send_realtime_update(self, event_type: str, instance: Any, config_name: str = None):\n        \"\"\"\n        Send real-time update to WebSocket subscribers.\n        \n        Args:\n            event_type (str): Type of event (create, update, delete)\n            instance (Any): The model instance\n            config_name (str, optional): Configuration name. Defaults to None.\n        \"\"\"\n        if not self.enable_realtime or event_type not in self.realtime_events:\n            return\n        \n        try:\n            from channels.layers import get_channel_layer\n            from asgiref.sync import async_to_sync\n        except ImportError:\n            logger.warning(\"Channels not installed. Real-time updates unavailable.\")\n            return\n        \n        channel_layer = get_channel_layer()\n        if not channel_layer:\n            return\n        \n        group_name = self.get_realtime_group_name(config_name)\n        \n        # Serialize the instance\n        serializer = self.get_serializer(instance)\n        \n        message = {\n            'type': 'list_update',\n            'event_type': event_type,\n            'data': serializer.data,\n            'config': config_name,\n            'timestamp': timezone.now().isoformat()\n        }\n        \n        async_to_sync(channel_layer.group_send)(group_name, message)\n    \n    def perform_create(self, serializer):\n        \"\"\"\n        Override to send real-time updates on create.\n        \"\"\"\n        instance = serializer.save()\n        self.send_realtime_update('create', instance)\n        return instance\n    \n    def perform_update(self, serializer):\n        \"\"\"\n        Override to send real-time updates on update.\n        \"\"\"\n        instance = serializer.save()\n        self.send_realtime_update('update', instance)\n        return instance\n    \n    def perform_destroy(self, instance):\n        \"\"\"\n        Override to send real-time updates on delete.\n        \"\"\"\n        self.send_realtime_update('delete', instance)\n        instance.delete()