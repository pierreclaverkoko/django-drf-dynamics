import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class BaseListBackend(ABC):
    """
    Abstract base class for list backends.
    
    List backends are responsible for processing list data from different sources
    (Django ORM, Elasticsearch, WebSocket, etc.) and returning standardized
    list responses with pagination, filtering, and sorting.
    """
    
    @abstractmethod
    def get_list_data(self, view, request, config, page=1, per_page=25, search="", ordering=""):
        """
        Get list data from the backend.
        
        Args:
            view: The view instance
            request: HTTP request object
            config: List configuration dictionary
            page: Page number
            per_page: Items per page
            search: Search term
            ordering: Ordering field
            
        Returns:
            Dict: Standardized list response
        """
        pass
    
    def build_list_response(self, items, total_count, page, per_page, config):
        """
        Build a standardized list response.
        
        Args:
            items: List of serialized items
            total_count: Total number of items
            page: Current page number
            per_page: Items per page
            config: List configuration
            
        Returns:
            Dict: Standardized response structure
        """
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            'data': items,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_next': page < total_pages,
                'has_previous': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'previous_page': page - 1 if page > 1 else None,
            },
            'meta': {
                'config_name': getattr(config, 'name', 'default'),
                'fields': config.get('fields', []),
                'search_enabled': config.get('enable_search', False),
                'filters_enabled': config.get('enable_filters', False),
                'sorting_enabled': config.get('enable_sorting', False),
            }
        }


class DjangoOrmListBackend(BaseListBackend):
    """
    List backend for Django ORM QuerySets.
    
    This backend processes Django QuerySets with filtering, searching,
    ordering, and pagination support.
    """
    
    def get_list_data(self, view, request, config, page=1, per_page=25, search="", ordering=""):
        """
        Get list data from Django ORM QuerySet.
        
        Args:
            view: The view instance
            request: HTTP request object
            config: List configuration dictionary
            page: Page number
            per_page: Items per page
            search: Search term
            ordering: Ordering field
            
        Returns:
            Dict: List response with Django ORM data
        """
        queryset = view.get_queryset()
        
        # Apply filtering
        queryset = self._apply_filters(queryset, view, request)
        
        # Apply search
        if search and config.get('enable_search', False):
            queryset = self._apply_search(queryset, search, config.get('search_fields', []))\n        \n        # Apply ordering\n        if ordering and config.get('enable_sorting', False):\n            queryset = self._apply_ordering(queryset, ordering, config.get('sorting_fields', []))\n        elif hasattr(view, 'ordering'):\n            queryset = queryset.order_by(*view.ordering)\n        \n        # Get total count before pagination\n        total_count = queryset.count()\n        \n        # Apply pagination\n        paginator = Paginator(queryset, per_page)\n        page_obj = paginator.get_page(page)\n        \n        # Serialize the data\n        serializer_class = self._get_list_serializer_class(view, config)\n        serializer = serializer_class(page_obj.object_list, many=True, context={'request': request})\n        \n        # Build and return response\n        return self.build_list_response(\n            items=serializer.data,\n            total_count=total_count,\n            page=page,\n            per_page=per_page,\n            config=config\n        )\n    \n    def _apply_filters(self, queryset, view, request):\n        \"\"\"\n        Apply filters to the queryset based on request parameters.\n        \n        Args:\n            queryset: Django QuerySet\n            view: View instance\n            request: HTTP request\n            \n        Returns:\n            QuerySet: Filtered queryset\n        \"\"\"\n        # Use the view's filter backends if available\n        if hasattr(view, 'filter_backends'):\n            for backend in view.filter_backends:\n                queryset = backend().filter_queryset(request, queryset, view)\n        \n        return queryset\n    \n    def _apply_search(self, queryset, search_term, search_fields):\n        \"\"\"\n        Apply search to the queryset.\n        \n        Args:\n            queryset: Django QuerySet\n            search_term: Search term\n            search_fields: List of fields to search in\n            \n        Returns:\n            QuerySet: Filtered queryset\n        \"\"\"\n        if not search_term or not search_fields:\n            return queryset\n        \n        search_q = Q()\n        for field in search_fields:\n            search_q |= Q(**{f\"{field}__icontains\": search_term})\n        \n        return queryset.filter(search_q)\n    \n    def _apply_ordering(self, queryset, ordering, allowed_fields):\n        \"\"\"\n        Apply ordering to the queryset.\n        \n        Args:\n            queryset: Django QuerySet\n            ordering: Ordering field (with optional - prefix for descending)\n            allowed_fields: List of allowed ordering fields\n            \n        Returns:\n            QuerySet: Ordered queryset\n        \"\"\"\n        # Remove - prefix to check if field is allowed\n        field_name = ordering.lstrip('-')\n        \n        if field_name in allowed_fields:\n            return queryset.order_by(ordering)\n        \n        return queryset\n    \n    def _get_list_serializer_class(self, view, config):\n        \"\"\"\n        Get the appropriate serializer class for list data.\n        \n        Args:\n            view: View instance\n            config: List configuration\n            \n        Returns:\n            Serializer class\n        \"\"\"\n        # Try to get list-specific serializer\n        if hasattr(view, 'get_serializer_class'):\n            return view.get_serializer_class()\n        \n        # Fallback to view's serializer_class\n        return getattr(view, 'serializer_class', None)


class ElasticsearchListBackend(BaseListBackend):
    """
    List backend for Elasticsearch DSL integration.
    
    This backend processes Elasticsearch documents with advanced search,
    filtering, aggregations, and pagination support.
    \n    Requires django-elasticsearch-dsl-drf to be installed.\n    \"\"\"\n    \n    def get_list_data(self, view, request, config, page=1, per_page=25, search=\"\", ordering=\"\"):\n        \"\"\"\n        Get list data from Elasticsearch.\n        \n        Args:\n            view: The view instance\n            request: HTTP request object\n            config: List configuration dictionary\n            page: Page number\n            per_page: Items per page\n            search: Search term\n            ordering: Ordering field\n            \n        Returns:\n            Dict: List response with Elasticsearch data\n        \"\"\"\n        try:\n            from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet\n        except ImportError:\n            raise ImportError(\"django-elasticsearch-dsl-drf is required for Elasticsearch backend\")\n        \n        if not isinstance(view, DocumentViewSet):\n            raise TypeError(\"View must inherit from DocumentViewSet for Elasticsearch backend\")\n        \n        # Get the document search\n        search_obj = view.document.search()\n        \n        # Apply filters using the view's filter backends\n        if hasattr(view, 'filter_backends'):\n            for backend in view.filter_backends:\n                search_obj = backend().filter_queryset(request, search_obj, view)\n        \n        # Apply search if enabled\n        if search and config.get('enable_search', False):\n            search_obj = self._apply_elasticsearch_search(search_obj, search, config.get('search_fields', []))\n        \n        # Apply ordering\n        if ordering and config.get('enable_sorting', False):\n            search_obj = self._apply_elasticsearch_ordering(search_obj, ordering)\n        \n        # Calculate pagination\n        offset = (page - 1) * per_page\n        \n        # Apply pagination to search\n        search_obj = search_obj[offset:offset + per_page]\n        \n        # Execute the search\n        response = search_obj.execute()\n        \n        # Get total count\n        total_count = response.hits.total.value if hasattr(response.hits.total, 'value') else response.hits.total\n        \n        # Serialize the data\n        serializer_class = self._get_list_serializer_class(view, config)\n        serializer = serializer_class(response, many=True, context={'request': request})\n        \n        # Build and return response\n        return self.build_list_response(\n            items=serializer.data,\n            total_count=total_count,\n            page=page,\n            per_page=per_page,\n            config=config\n        )\n    \n    def _apply_elasticsearch_search(self, search_obj, search_term, search_fields):\n        \"\"\"\n        Apply search to Elasticsearch query.\n        \n        Args:\n            search_obj: Elasticsearch Search object\n            search_term: Search term\n            search_fields: List of fields to search in\n            \n        Returns:\n            Search: Updated search object\n        \"\"\"\n        if not search_term or not search_fields:\n            return search_obj\n        \n        # Use multi_match query for searching across multiple fields\n        return search_obj.query(\n            'multi_match',\n            query=search_term,\n            fields=search_fields,\n            fuzziness='AUTO'\n        )\n    \n    def _apply_elasticsearch_ordering(self, search_obj, ordering):\n        \"\"\"\n        Apply ordering to Elasticsearch query.\n        \n        Args:\n            search_obj: Elasticsearch Search object\n            ordering: Ordering field\n            \n        Returns:\n            Search: Updated search object\n        \"\"\"\n        if ordering.startswith('-'):\n            # Descending order\n            field_name = ordering[1:]\n            return search_obj.sort({field_name: {'order': 'desc'}})\n        else:\n            # Ascending order\n            return search_obj.sort({ordering: {'order': 'asc'}})\n    \n    def _get_list_serializer_class(self, view, config):\n        \"\"\"\n        Get the appropriate serializer class for Elasticsearch data.\n        \n        Args:\n            view: View instance\n            config: List configuration\n            \n        Returns:\n            Serializer class\n        \"\"\"\n        # Try to get document serializer\n        if hasattr(view, 'serializer_class'):\n            return view.serializer_class\n        \n        # Fallback to a default document serializer\n        from django_elasticsearch_dsl_drf.serializers import DocumentSerializer\n        return DocumentSerializer


class WebSocketListBackend(BaseListBackend):\n    \"\"\"\n    List backend for WebSocket-based real-time data.\n    \n    This backend provides real-time list updates via WebSocket connections,\n    allowing for live data updates without page refreshes.\n    \n    Requires channels for WebSocket support.\n    \"\"\"\n    \n    def get_list_data(self, view, request, config, page=1, per_page=25, search=\"\", ordering=\"\"):\n        \"\"\"\n        Get list data with WebSocket connection information.\n        \n        This method returns initial list data along with WebSocket connection\n        details for real-time updates.\n        \n        Args:\n            view: The view instance\n            request: HTTP request object\n            config: List configuration dictionary\n            page: Page number\n            per_page: Items per page\n            search: Search term\n            ordering: Ordering field\n            \n        Returns:\n            Dict: List response with WebSocket connection info\n        \"\"\"\n        # First, get the initial data using Django ORM backend\n        orm_backend = DjangoOrmListBackend()\n        initial_data = orm_backend.get_list_data(view, request, config, page, per_page, search, ordering)\n        \n        # Add WebSocket connection information\n        websocket_info = self._get_websocket_info(view, config)\n        \n        # Enhance the response with WebSocket details\n        initial_data['websocket'] = websocket_info\n        initial_data['realtime_enabled'] = True\n        \n        return initial_data\n    \n    def _get_websocket_info(self, view, config):\n        \"\"\"\n        Get WebSocket connection information.\n        \n        Args:\n            view: View instance\n            config: List configuration\n            \n        Returns:\n            Dict: WebSocket connection details\n        \"\"\"\n        try:\n            from channels.layers import get_channel_layer\n        except ImportError:\n            logger.warning(\"Channels not installed. WebSocket functionality unavailable.\")\n            return {\n                'available': False,\n                'error': 'Channels not installed'\n            }\n        \n        channel_layer = get_channel_layer()\n        if not channel_layer:\n            return {\n                'available': False,\n                'error': 'Channel layer not configured'\n            }\n        \n        # Generate WebSocket group name\n        group_name = self._get_websocket_group_name(view, config)\n        \n        return {\n            'available': True,\n            'group_name': group_name,\n            'url': f'/ws/lists/{group_name}/',\n            'protocols': ['json'],\n            'events': getattr(view, 'realtime_events', ['create', 'update', 'delete']),\n            'connection_instructions': {\n                'connect': f'Connect to WebSocket at: /ws/lists/{group_name}/',\n                'subscribe': {\n                    'type': 'subscribe',\n                    'group': group_name\n                },\n                'unsubscribe': {\n                    'type': 'unsubscribe',\n                    'group': group_name\n                }\n            }\n        }\n    \n    def _get_websocket_group_name(self, view, config):\n        \"\"\"\n        Generate WebSocket group name for the list.\n        \n        Args:\n            view: View instance\n            config: List configuration\n            \n        Returns:\n            str: WebSocket group name\n        \"\"\"\n        model_name = view.queryset.model._meta.label_lower\n        config_name = getattr(config, 'name', 'default')\n        \n        return f\"list_{model_name}_{config_name}\"