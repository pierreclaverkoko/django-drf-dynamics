import logging
from abc import ABC, abstractmethod

from django.core.paginator import Paginator
from django.db.models import Q

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
            "data": items,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_previous": page > 1,
                "next_page": page + 1 if page < total_pages else None,
                "previous_page": page - 1 if page > 1 else None,
            },
            "meta": {
                "config_name": getattr(config, "name", "default"),
                "fields": config.get("fields", []),
                "search_enabled": config.get("enable_search", False),
                "filters_enabled": config.get("enable_filters", False),
                "sorting_enabled": config.get("enable_sorting", False),
            },
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
        if search and config.get("enable_search", False):
            queryset = self._apply_search(queryset, search, config.get("search_fields", []))

        # Apply ordering
        if ordering and config.get("enable_sorting", False):
            queryset = self._apply_ordering(queryset, ordering, config.get("sorting_fields", []))
        elif hasattr(view, "ordering"):
            queryset = queryset.order_by(*view.ordering)

        # Get total count before pagination
        total_count = queryset.count()

        # Apply pagination
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        # Serialize the data
        serializer_class = self._get_list_serializer_class(view, config)
        serializer = serializer_class(page_obj.object_list, many=True, context={"request": request})

        # Build and return response
        return self.build_list_response(
            items=serializer.data, total_count=total_count, page=page, per_page=per_page, config=config
        )

    def _apply_filters(self, queryset, view, request):
        """
        Apply filters to the queryset based on request parameters.

        Args:
            queryset: Django QuerySet
            view: View instance
            request: HTTP request

        Returns:
            QuerySet: Filtered queryset
        """
        # Use the view's filter backends if available
        if hasattr(view, "filter_backends"):
            for backend in view.filter_backends:
                queryset = backend().filter_queryset(request, queryset, view)

        return queryset

    def _apply_search(self, queryset, search_term, search_fields):
        """
        Apply search to the queryset.

        Args:
            queryset: Django QuerySet
            search_term: Search term
            search_fields: List of fields to search in

        Returns:
            QuerySet: Filtered queryset
        """
        if not search_term or not search_fields:
            return queryset

        search_q = Q()
        for field in search_fields:
            search_q |= Q(**{f"{field}__icontains": search_term})

        return queryset.filter(search_q)

    def _apply_ordering(self, queryset, ordering, allowed_fields):
        """
        Apply ordering to the queryset.

        Args:
            queryset: Django QuerySet
            ordering: Ordering field (with optional - prefix for descending)
            allowed_fields: List of allowed ordering fields

        Returns:
            QuerySet: Ordered queryset
        """
        # Remove - prefix to check if field is allowed
        field_name = ordering.lstrip("-")

        if field_name in allowed_fields:
            return queryset.order_by(ordering)

        return queryset

    def _get_list_serializer_class(self, view, config):
        """
        Get the appropriate serializer class for list data.

        Args:
            view: View instance
            config: List configuration

        Returns:
            Serializer class
        """
        # Try to get list-specific serializer
        if hasattr(view, "get_serializer_class"):
            return view.get_serializer_class()

        # Fallback to view's serializer_class
        return getattr(view, "serializer_class", None)


class ElasticsearchListBackend(BaseListBackend):
    """
    List backend for Elasticsearch DSL integration.

    This backend processes Elasticsearch documents with advanced search,
    filtering, aggregations, and pagination support.

    Requires django-elasticsearch-dsl-drf to be installed.
    """

    def get_list_data(self, view, request, config, page=1, per_page=25, search="", ordering=""):
        """
        Get list data from Elasticsearch.

        Args:
            view: The view instance
            request: HTTP request object
            config: List configuration dictionary
            page: Page number
            per_page: Items per page
            search: Search term
            ordering: Ordering field

        Returns:
            Dict: List response with Elasticsearch data
        """
        try:
            from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet
        except ImportError:
            raise ImportError("django-elasticsearch-dsl-drf is required for Elasticsearch backend")

        if not isinstance(view, DocumentViewSet):
            raise TypeError("View must inherit from DocumentViewSet for Elasticsearch backend")

        # Get the document search
        search_obj = view.document.search()

        # Apply filters using the view's filter backends
        if hasattr(view, "filter_backends"):
            for backend in view.filter_backends:
                search_obj = backend().filter_queryset(request, search_obj, view)

        # Apply search if enabled
        if search and config.get("enable_search", False):
            search_obj = self._apply_elasticsearch_search(search_obj, search, config.get("search_fields", []))

        # Apply ordering
        if ordering and config.get("enable_sorting", False):
            search_obj = self._apply_elasticsearch_ordering(search_obj, ordering)

        # Calculate pagination
        offset = (page - 1) * per_page

        # Apply pagination to search
        search_obj = search_obj[offset : offset + per_page]

        # Execute the search
        response = search_obj.execute()

        # Get total count
        total_count = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total

        # Serialize the data
        serializer_class = self._get_list_serializer_class(view, config)
        serializer = serializer_class(response, many=True, context={"request": request})

        # Build and return response
        return self.build_list_response(
            items=serializer.data, total_count=total_count, page=page, per_page=per_page, config=config
        )

    def _apply_elasticsearch_search(self, search_obj, search_term, search_fields):
        """
        Apply search to Elasticsearch query.

        Args:
            search_obj: Elasticsearch Search object
            search_term: Search term
            search_fields: List of fields to search in

        Returns:
            Search: Updated search object
        """
        if not search_term or not search_fields:
            return search_obj

        # Use multi_match query for searching across multiple fields
        return search_obj.query("multi_match", query=search_term, fields=search_fields, fuzziness="AUTO")

    def _apply_elasticsearch_ordering(self, search_obj, ordering):
        """
        Apply ordering to Elasticsearch query.

        Args:
            search_obj: Elasticsearch Search object
            ordering: Ordering field

        Returns:
            Search: Updated search object
        """
        if ordering.startswith("-"):
            # Descending order
            field_name = ordering[1:]
            return search_obj.sort({field_name: {"order": "desc"}})
        else:
            # Ascending order
            return search_obj.sort({ordering: {"order": "asc"}})

    def _get_list_serializer_class(self, view, config):
        """
        Get the appropriate serializer class for Elasticsearch data.

        Args:
            view: View instance
            config: List configuration

        Returns:
            Serializer class
        """
        # Try to get document serializer
        if hasattr(view, "serializer_class"):
            return view.serializer_class

        # Fallback to a default document serializer
        from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

        return DocumentSerializer


class WebSocketListBackend(BaseListBackend):
    """
    List backend for WebSocket-based real-time data.

    This backend provides real-time list updates via WebSocket connections,
    allowing for live data updates without page refreshes.

    Requires channels for WebSocket support.
    """

    def get_list_data(self, view, request, config, page=1, per_page=25, search="", ordering=""):
        """
        Get list data with WebSocket connection information.

        This method returns initial list data along with WebSocket connection
        details for real-time updates.

        Args:
            view: The view instance
            request: HTTP request object
            config: List configuration dictionary
            page: Page number
            per_page: Items per page
            search: Search term
            ordering: Ordering field

        Returns:
            Dict: List response with WebSocket connection info
        """
        # First, get the initial data using Django ORM backend
        orm_backend = DjangoOrmListBackend()
        initial_data = orm_backend.get_list_data(view, request, config, page, per_page, search, ordering)

        # Add WebSocket connection information
        websocket_info = self._get_websocket_info(view, config)

        # Enhance the response with WebSocket details
        initial_data["websocket"] = websocket_info
        initial_data["realtime_enabled"] = True

        return initial_data

    def _get_websocket_info(self, view, config):
        """
        Get WebSocket connection information.

        Args:
            view: View instance
            config: List configuration

        Returns:
            Dict: WebSocket connection details
        """
        try:
            from channels.layers import get_channel_layer
        except ImportError:
            logger.warning("Channels not installed. WebSocket functionality unavailable.")
            return {"available": False, "error": "Channels not installed"}

        channel_layer = get_channel_layer()
        if not channel_layer:
            return {"available": False, "error": "Channel layer not configured"}

        # Generate WebSocket group name
        group_name = self._get_websocket_group_name(view, config)

        return {
            "available": True,
            "group_name": group_name,
            "url": f"/ws/lists/{group_name}/",
            "protocols": ["json"],
            "events": getattr(view, "realtime_events", ["create", "update", "delete"]),
            "connection_instructions": {
                "connect": f"Connect to WebSocket at: /ws/lists/{group_name}/",
                "subscribe": {"type": "subscribe", "group": group_name},
                "unsubscribe": {"type": "unsubscribe", "group": group_name},
            },
        }

    def _get_websocket_group_name(self, view, config):
        """
        Generate WebSocket group name for the list.

        Args:
            view: View instance
            config: List configuration

        Returns:
            str: WebSocket group name
        """
        model_name = view.queryset.model._meta.label_lower
        config_name = getattr(config, "name", "default")

        return f"list_{model_name}_{config_name}"
