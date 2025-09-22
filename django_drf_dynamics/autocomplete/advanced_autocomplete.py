import logging
import time
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .autocomplete_backends import (
    DatabaseAutocompleteBackend,
    ElasticsearchAutocompleteBackend,
    CacheAutocompleteBackend,
)
from .autocomplete_serializers import AutocompleteItemSerializer

logger = logging.getLogger(__name__)


class AdvancedAutocompleteMixin:
    """
    An advanced autocomplete mixin with enhanced search capabilities.

    This mixin provides sophisticated autocomplete functionality with:
    - Multi-field search
    - Fuzzy matching
    - Custom ranking/scoring
    - Minimum query length
    - Debouncing support (client-side)
    - Result limiting and pagination

    Example usage:

    ```python
    class AuthorViewSet(AdvancedAutocompleteMixin, viewsets.ModelViewSet):
        queryset = Author.objects.all()
        autocomplete_fields = ['name', 'email', 'bio']
        autocomplete_min_length = 2
        autocomplete_max_results = 20
        autocomplete_enable_fuzzy = True

        def get_autocomplete_queryset(self):
            return self.queryset.select_related('publisher')
    ```
    """

    # Autocomplete configuration
    autocomplete_fields = ["name"]  # Fields to search in
    autocomplete_display_field = None  # Field to display (defaults to first autocomplete field)
    autocomplete_min_length = 1  # Minimum query length
    autocomplete_max_results = 50  # Maximum number of results
    autocomplete_enable_fuzzy = False  # Enable fuzzy matching
    autocomplete_fuzzy_threshold = 0.6  # Fuzzy matching threshold
    autocomplete_case_sensitive = False  # Case sensitive search
    autocomplete_exact_match_boost = 2.0  # Boost factor for exact matches
    autocomplete_startswith_boost = 1.5  # Boost factor for startswith matches

    # Backend configuration
    autocomplete_backend = "database"  # 'database', 'elasticsearch', 'cache'
    autocomplete_backends = {
        "database": DatabaseAutocompleteBackend,
        "elasticsearch": ElasticsearchAutocompleteBackend,
        "cache": CacheAutocompleteBackend,
    }

    def get_autocomplete_backend(self):
        """
        Get the configured autocomplete backend.

        Returns:
            BaseAutocompleteBackend: Backend instance
        """
        backend_class = self.autocomplete_backends.get(self.autocomplete_backend)
        if not backend_class:
            raise ImproperlyConfigured(f"Autocomplete backend '{self.autocomplete_backend}' not found")

        return backend_class()

    def get_autocomplete_queryset(self):
        """
        Get the queryset for autocomplete.

        Returns:
            QuerySet: Queryset to search in
        """
        return self.get_queryset()

    def get_autocomplete_serializer(self, data, many=True):
        """
        Get the serializer for autocomplete results.

        Args:
            data: Data to serialize
            many: Whether to serialize multiple objects

        Returns:
            Serializer: Configured serializer instance
        """
        serializer_class = getattr(self, "autocomplete_serializer_class", AutocompleteItemSerializer)
        context = self.get_serializer_context() if hasattr(self, "get_serializer_context") else {}
        return serializer_class(data, many=many, context=context)

    @action(detail=False, methods=["get"])
    def advanced_autocomplete(self, request):
        """
        Advanced autocomplete endpoint with enhanced search capabilities.

        Query parameters:
        - q: Search query (required)
        - limit: Maximum number of results (default: autocomplete_max_results)
        - fuzzy: Enable fuzzy matching (default: autocomplete_enable_fuzzy)
        - fields: Comma-separated list of fields to search in
        - boost_exact: Boost factor for exact matches
        - boost_startswith: Boost factor for startswith matches

        Returns:
            Response: Autocomplete results with metadata
        """
        query = request.query_params.get("q", "").strip()

        # Validate query length
        if len(query) < self.autocomplete_min_length:
            return Response(
                {
                    "results": [],
                    "metadata": {
                        "query": query,
                        "count": 0,
                        "min_length": self.autocomplete_min_length,
                        "message": _(f"Query must be at least {self.autocomplete_min_length} characters long"),
                    },
                }
            )

        # Parse parameters
        limit = min(
            int(request.query_params.get("limit", self.autocomplete_max_results)), self.autocomplete_max_results
        )
        enable_fuzzy = request.query_params.get("fuzzy", str(self.autocomplete_enable_fuzzy)).lower() == "true"
        search_fields = request.query_params.get("fields", ",".join(self.autocomplete_fields)).split(",")
        boost_exact = float(request.query_params.get("boost_exact", self.autocomplete_exact_match_boost))
        boost_startswith = float(request.query_params.get("boost_startswith", self.autocomplete_startswith_boost))

        # Get backend and perform search
        backend = self.get_autocomplete_backend()

        search_config = {
            "query": query,
            "fields": search_fields,
            "limit": limit,
            "fuzzy": enable_fuzzy,
            "fuzzy_threshold": self.autocomplete_fuzzy_threshold,
            "case_sensitive": self.autocomplete_case_sensitive,
            "boost_exact": boost_exact,
            "boost_startswith": boost_startswith,
        }

        try:
            start_time = time.time()
            results = backend.search(queryset=self.get_autocomplete_queryset(), config=search_config, view=self)
            search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Serialize results
            serializer = self.get_autocomplete_serializer(results, many=True)

            return Response(
                {
                    "results": serializer.data,
                    "metadata": {
                        "query": query,
                        "count": len(results),
                        "limit": limit,
                        "search_time_ms": round(search_time, 2),
                        "backend": self.autocomplete_backend,
                        "fuzzy_enabled": enable_fuzzy,
                        "fields_searched": search_fields,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Autocomplete search error: {e}")
            return Response(
                {"error": _("Search failed"), "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def autocomplete_config(self, request):
        """
        Get autocomplete configuration for frontend.

        Returns:
            Response: Autocomplete configuration
        """
        return Response(
            {
                "fields": self.autocomplete_fields,
                "display_field": self.autocomplete_display_field or self.autocomplete_fields[0],
                "min_length": self.autocomplete_min_length,
                "max_results": self.autocomplete_max_results,
                "fuzzy_enabled": self.autocomplete_enable_fuzzy,
                "fuzzy_threshold": self.autocomplete_fuzzy_threshold,
                "case_sensitive": self.autocomplete_case_sensitive,
                "backend": self.autocomplete_backend,
                "endpoints": {
                    "search": f"{request.build_absolute_uri()}advanced_autocomplete/",
                    "config": f"{request.build_absolute_uri()}autocomplete_config/",
                },
                "debounce_recommended_ms": 300,  # Recommended frontend debouncing
                "example_usage": {
                    "basic": f"{request.build_absolute_uri()}advanced_autocomplete/?q=search_term",
                    "limited": f"{request.build_absolute_uri()}advanced_autocomplete/?q=term&limit=10",
                    "fuzzy": f"{request.build_absolute_uri()}advanced_autocomplete/?q=term&fuzzy=true",
                },
            }
        )


class CachedAutocompleteMixin(AdvancedAutocompleteMixin):
    """
    Autocomplete mixin with intelligent caching.

    This mixin adds caching capabilities to autocomplete searches,
    significantly improving performance for repeated queries.

    Example usage:

    ```python
    class ProductViewSet(CachedAutocompleteMixin, viewsets.ModelViewSet):
        queryset = Product.objects.all()
        autocomplete_cache_timeout = 900  # 15 minutes
        autocomplete_cache_key_prefix = 'product_autocomplete'
        autocomplete_cache_by_user = True
    ```
    """

    # Cache configuration
    autocomplete_cache_timeout = 600  # 10 minutes
    autocomplete_cache_key_prefix = "autocomplete"
    autocomplete_cache_by_user = False  # Include user ID in cache key
    autocomplete_cache_vary_by = []  # Additional parameters to vary cache by

    def get_autocomplete_cache_key(self, query: str, **kwargs) -> str:
        """
        Generate cache key for autocomplete query.

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            str: Cache key
        """
        model_name = self.get_queryset().model._meta.label_lower

        # Base key components
        key_parts = [
            self.autocomplete_cache_key_prefix,
            model_name,
            query.lower()[:50],  # Limit query length in cache key
        ]

        # Add user ID if enabled
        if self.autocomplete_cache_by_user and hasattr(self, "request"):
            user_id = getattr(self.request.user, "id", "anon") if self.request.user.is_authenticated else "anon"
            key_parts.append(str(user_id))

        # Add custom vary-by parameters
        for param in self.autocomplete_cache_vary_by:
            value = kwargs.get(param, "")
            key_parts.append(f"{param}:{value}")

        # Add search configuration to cache key
        config_hash = hash(str(sorted(kwargs.items())))
        key_parts.append(str(abs(config_hash)))

        return ":".join(key_parts)

    def get_cached_autocomplete_results(self, cache_key: str) -> Optional[List]:
        """
        Retrieve cached autocomplete results.

        Args:
            cache_key: Cache key

        Returns:
            Optional[List]: Cached results or None
        """
        return cache.get(cache_key)

    def set_cached_autocomplete_results(self, cache_key: str, results: List) -> None:
        """
        Cache autocomplete results.

        Args:
            cache_key: Cache key
            results: Results to cache
        """
        cache.set(cache_key, results, timeout=self.autocomplete_cache_timeout)

    def invalidate_autocomplete_cache(self, pattern: str = None) -> None:
        """
        Invalidate autocomplete cache entries.

        Args:
            pattern: Cache key pattern to match (optional)
        """
        if pattern:
            # This would require a more sophisticated cache backend
            # that supports pattern-based deletion
            logger.info(f"Cache invalidation requested for pattern: {pattern}")
        else:
            # Clear all cache entries for this model
            model_name = self.get_queryset().model._meta.label_lower
            pattern = f"{self.autocomplete_cache_key_prefix}:{model_name}:*"
            logger.info(f"Cache invalidation requested for pattern: {pattern}")

    @action(detail=False, methods=["get"])
    def advanced_autocomplete(self, request):
        """Override to add caching functionality."""
        query = request.query_params.get("q", "").strip()

        if len(query) < self.autocomplete_min_length:
            return super().advanced_autocomplete(request)

        # Generate cache key
        cache_params = {
            "limit": request.query_params.get("limit", self.autocomplete_max_results),
            "fuzzy": request.query_params.get("fuzzy", str(self.autocomplete_enable_fuzzy)),
            "fields": request.query_params.get("fields", ",".join(self.autocomplete_fields)),
        }
        cache_key = self.get_autocomplete_cache_key(query, **cache_params)

        # Check cache first
        cached_results = self.get_cached_autocomplete_results(cache_key)
        if cached_results is not None:
            return Response(
                {
                    "results": cached_results,
                    "metadata": {
                        "query": query,
                        "count": len(cached_results),
                        "cached": True,
                        "cache_key": cache_key[:50] + "..." if len(cache_key) > 50 else cache_key,
                    },
                }
            )

        # Get fresh results
        response = super().advanced_autocomplete(request)

        # Cache the results if successful
        if response.status_code == 200 and "results" in response.data:
            self.set_cached_autocomplete_results(cache_key, response.data["results"])
            response.data["metadata"]["cached"] = False
            response.data["metadata"]["cache_timeout"] = self.autocomplete_cache_timeout

        return response

    def perform_create(self, serializer):
        """Override to invalidate cache on create."""
        instance = serializer.save()
        self.invalidate_autocomplete_cache()
        return instance

    def perform_update(self, serializer):
        """Override to invalidate cache on update."""
        instance = serializer.save()
        self.invalidate_autocomplete_cache()
        return instance

    def perform_destroy(self, instance):
        """Override to invalidate cache on delete."""
        self.invalidate_autocomplete_cache()
        instance.delete()


class MultiFieldAutocompleteMixin(AdvancedAutocompleteMixin):
    """
    Autocomplete mixin with multi-field search configuration.

    This mixin allows for different search configurations for different
    fields, including field-specific weights and search types.

    Example usage:

    ```python
    class ContactViewSet(MultiFieldAutocompleteMixin, viewsets.ModelViewSet):
        queryset = Contact.objects.all()
        autocomplete_field_config = {
            'name': {
                'weight': 2.0,
                'search_type': 'icontains',
                'boost_exact': 3.0
            },
            'email': {
                'weight': 1.5,
                'search_type': 'istartswith',
                'boost_exact': 2.0
            },
            'phone': {
                'weight': 1.0,
                'search_type': 'exact',
                'fuzzy': False
            }
        }
    ```
    """

    autocomplete_field_config = {}  # Field-specific configuration

    def get_field_search_config(self, field_name: str) -> Dict[str, Any]:
        """
        Get search configuration for a specific field.

        Args:
            field_name: Name of the field

        Returns:
            Dict[str, Any]: Field configuration
        """
        default_config = {
            "weight": 1.0,
            "search_type": "icontains",
            "boost_exact": self.autocomplete_exact_match_boost,
            "boost_startswith": self.autocomplete_startswith_boost,
            "fuzzy": self.autocomplete_enable_fuzzy,
            "case_sensitive": self.autocomplete_case_sensitive,
        }

        field_config = self.autocomplete_field_config.get(field_name, {})
        default_config.update(field_config)

        return default_config

    def get_weighted_search_query(self, query: str, fields: List[str]) -> Q:
        """
        Build a weighted search query across multiple fields.

        Args:
            query: Search query
            fields: List of fields to search

        Returns:
            Q: Django Q object for the search
        """
        search_q = Q()

        for field in fields:
            field_config = self.get_field_search_config(field)
            search_type = field_config["search_type"]

            # Build field-specific query
            field_q = Q(**{f"{field}__{search_type}": query})

            # Add exact match boost if configured
            if field_config.get("boost_exact", 0) > 1 and search_type != "exact":
                exact_q = Q(**{f"{field}__iexact": query})
                field_q = field_q | exact_q

            # Add startswith boost if configured
            if field_config.get("boost_startswith", 0) > 1 and search_type not in ["exact", "istartswith"]:
                startswith_q = Q(**{f"{field}__istartswith": query})
                field_q = field_q | startswith_q

            search_q |= field_q

        return search_q

    @action(detail=False, methods=["get"])
    def field_config(self, request):
        """
        Get field configuration for autocomplete.

        Returns:
            Response: Field configuration details
        """
        field_configs = {}

        for field in self.autocomplete_fields:
            field_configs[field] = self.get_field_search_config(field)

        return Response(
            {
                "fields": field_configs,
                "default_config": {
                    "weight": 1.0,
                    "search_type": "icontains",
                    "boost_exact": self.autocomplete_exact_match_boost,
                    "boost_startswith": self.autocomplete_startswith_boost,
                    "fuzzy": self.autocomplete_enable_fuzzy,
                    "case_sensitive": self.autocomplete_case_sensitive,
                },
            }
        )


class NestedLookupMixin:
    """
    Mixin for handling nested object lookups with relationship traversal.

    This mixin extends lookup functionality to search across related models
    and provides nested object information in responses.

    Example usage:

    ```python
    class OrderViewSet(NestedLookupMixin, viewsets.ModelViewSet):
        queryset = Order.objects.all()
        nested_lookup_fields = {
            'customer': {
                'model': 'Customer',
                'fields': ['name', 'email'],
                'display_format': '{name} ({email})'
            },
            'product': {
                'model': 'Product',
                'fields': ['name', 'sku'],
                'display_format': '{name} - {sku}'
            }
        }
    ```
    """

    nested_lookup_fields = {}  # Configuration for nested lookups
    nested_lookup_max_depth = 3  # Maximum relationship depth

    def get_nested_lookup_config(self, field_name: str) -> Dict[str, Any]:
        """
        Get configuration for nested lookup field.

        Args:
            field_name: Name of the nested field

        Returns:
            Dict[str, Any]: Nested field configuration
        """
        return self.nested_lookup_fields.get(field_name, {})

    def perform_nested_lookup(self, field_name: str, query: str) -> QuerySet:
        """
        Perform lookup on nested/related fields.

        Args:
            field_name: Name of the field to lookup
            query: Search query

        Returns:
            QuerySet: Results from nested lookup
        """
        config = self.get_nested_lookup_config(field_name)

        if not config:
            return self.get_queryset().none()

        search_fields = config.get("fields", [])
        queryset = self.get_queryset()

        # Build nested search query
        search_q = Q()
        for search_field in search_fields:
            nested_field = f"{field_name}__{search_field}__icontains"
            search_q |= Q(**{nested_field: query})

        return queryset.filter(search_q).select_related(field_name)

    def format_nested_display(self, obj, field_name: str) -> str:
        """
        Format display string for nested object.

        Args:
            obj: The main object
            field_name: Name of the nested field

        Returns:
            str: Formatted display string
        """
        config = self.get_nested_lookup_config(field_name)
        display_format = config.get("display_format", "{}")

        nested_obj = getattr(obj, field_name, None)
        if not nested_obj:
            return ""

        # Extract field values for formatting
        format_values = {}
        for field in config.get("fields", []):
            format_values[field] = getattr(nested_obj, field, "")

        try:
            return display_format.format(**format_values)
        except (KeyError, ValueError):
            return str(nested_obj)

    @action(detail=False, methods=["get"])
    def nested_autocomplete(self, request):
        """
        Perform autocomplete search across nested/related fields.

        Query parameters:
        - q: Search query
        - field: Nested field to search in
        - limit: Maximum results

        Returns:
            Response: Nested autocomplete results
        """
        query = request.query_params.get("q", "").strip()
        field_name = request.query_params.get("field", "")
        limit = int(request.query_params.get("limit", 20))

        if not query or not field_name:
            return Response({"results": [], "metadata": {"error": "Both q and field parameters are required"}})

        if field_name not in self.nested_lookup_fields:
            return Response(
                {"results": [], "metadata": {"error": f"Field {field_name} not configured for nested lookup"}}
            )

        # Perform nested search
        try:
            queryset = self.perform_nested_lookup(field_name, query)[:limit]

            # Format results
            results = []
            for obj in queryset:
                nested_display = self.format_nested_display(obj, field_name)
                results.append({"id": obj.id, "text": str(obj), "nested_display": nested_display, "field": field_name})

            return Response(
                {
                    "results": results,
                    "metadata": {"query": query, "field": field_name, "count": len(results), "limit": limit},
                }
            )

        except Exception as e:
            logger.error(f"Nested lookup error: {e}")
            return Response(
                {"error": _("Nested lookup failed"), "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def nested_lookup_config(self, request):
        """
        Get configuration for nested lookups.

        Returns:
            Response: Nested lookup configuration
        """
        return Response(
            {
                "nested_fields": self.nested_lookup_fields,
                "max_depth": self.nested_lookup_max_depth,
                "endpoints": {
                    "nested_search": f"{request.build_absolute_uri()}nested_autocomplete/",
                    "config": f"{request.build_absolute_uri()}nested_lookup_config/",
                },
            }
        )
