import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from django.core.cache import cache
from django.db.models import Q, QuerySet
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class BaseAutocompleteBackend(ABC):
    """
    Abstract base class for autocomplete backends.

    Autocomplete backends handle the actual search implementation
    for different data sources and search algorithms.
    """

    @abstractmethod
    def search(self, queryset: QuerySet, config: Dict[str, Any], view: Any) -> List[Any]:
        """
        Perform autocomplete search.

        Args:
            queryset: QuerySet to search in
            config: Search configuration
            view: View instance

        Returns:
            List[Any]: Search results
        """
        pass


class DatabaseAutocompleteBackend(BaseAutocompleteBackend):
    """
    Database-based autocomplete backend using Django ORM.

    This backend performs autocomplete searches using Django's
    database query capabilities with intelligent ranking.
    """

    def search(self, queryset: QuerySet, config: Dict[str, Any], view: Any) -> List[Any]:
        """
        Perform database search with intelligent ranking.

        Args:
            queryset: Django QuerySet
            config: Search configuration
            view: View instance

        Returns:
            List: Ranked search results
        """
        query = config["query"]
        fields = config["fields"]
        limit = config["limit"]
        fuzzy = config.get("fuzzy", False)
        case_sensitive = config.get("case_sensitive", False)

        # Build search query
        search_q = self._build_search_query(query, fields, case_sensitive)

        # Execute search
        results = list(queryset.filter(search_q)[: limit * 2])  # Get more for ranking

        # Apply fuzzy matching if enabled
        if fuzzy and results:
            results = self._apply_fuzzy_matching(results, query, fields, config)

        # Rank and limit results
        ranked_results = self._rank_results(results, query, fields, config)

        return ranked_results[:limit]

    def _build_search_query(self, query: str, fields: List[str], case_sensitive: bool = False) -> Q:
        """
        Build Django Q object for search.

        Args:
            query: Search query
            fields: Fields to search in
            case_sensitive: Whether search is case sensitive

        Returns:
            Q: Django Q object
        """
        search_q = Q()
        lookup_suffix = "contains" if case_sensitive else "icontains"

        for field in fields:
            search_q |= Q(**{f"{field}__{lookup_suffix}": query})

        return search_q

    def _get_model_field_string_value(self, instance, field_path):
        """
        Retrieves the string representation of a value from a Django model instance,
        handling single fields and lookups across relations (e.g., 'course__title').
        """
        if not field_path:
            return ""

        # Start with the model instance
        current_object = instance

        # Split the path by the double-underscore '__'
        lookups = field_path.split("__")

        # Traverse the lookups
        for i, lookup in enumerate(lookups):
            if current_object is None:
                # If any object in the chain is None (e.g., a ForeignKey is null), stop
                return ""

            # Use getattr to get the attribute (field or related object)
            value = getattr(current_object, lookup, None)

            # Handle the type of value retrieved

            # 1. If it's the last part of the path, we have the final value
            if i == len(lookups) - 1:
                # Check for a ManyToMany/Reverse relation (the value is a manager)
                if hasattr(value, "all") and callable(value.all):
                    # Return a comma-separated list of related objects' string representations
                    return ", ".join(str(obj) for obj in value.all())

                # For all other fields (Char, Int, Date, or a related object's __str__),
                # simply convert it to a string.
                return str(value) if value is not None else ""

            # 2. If it's an intermediate step, move to the next object
            else:
                # This must be a relation (ForeignKey, OneToOne)
                # Set the retrieved value as the object for the next iteration
                current_object = value

        # Fallback return (should rarely be hit)
        return ""

    def _apply_fuzzy_matching(
        self, results: List[Any], query: str, fields: List[str], config: Dict[str, Any]
    ) -> List[Any]:
        """
        Apply fuzzy matching to results.

        Args:
            results: Initial search results
            query: Search query
            fields: Search fields
            config: Search configuration

        Returns:
            List: Fuzzy-matched results
        """
        fuzzy_threshold = config.get("fuzzy_threshold", 0.6)
        fuzzy_results = []

        for result in results:
            max_similarity = 0.0

            for field in fields:
                field_value = self._get_model_field_string_value(result, field)  # str(getattr(result, field, ""))
                similarity = SequenceMatcher(None, query.lower(), field_value.lower()).ratio()
                max_similarity = max(max_similarity, similarity)

            if max_similarity >= fuzzy_threshold:
                # Store similarity for ranking
                result._autocomplete_similarity = max_similarity
                fuzzy_results.append(result)

        return fuzzy_results

    def _rank_results(self, results: List[Any], query: str, fields: List[str], config: Dict[str, Any]) -> List[Any]:
        """
        Rank search results by relevance.

        Args:
            results: Search results to rank
            query: Search query
            fields: Search fields
            config: Search configuration

        Returns:
            List: Ranked results
        """
        boost_exact = config.get("boost_exact", 2.0)
        boost_startswith = config.get("boost_startswith", 1.5)

        scored_results = []

        for result in results:
            score = 0.0

            # Base similarity score if available
            if hasattr(result, "_autocomplete_similarity"):
                score = result._autocomplete_similarity
            else:
                score = 0.5  # Default base score

            # Apply boosts
            for field in fields:
                field_value = str(getattr(result, field, "")).lower()
                query_lower = query.lower()

                # Exact match boost
                if field_value == query_lower:
                    score *= boost_exact
                    break  # Exact match is best, no need to check other fields

                # Starts with boost
                elif field_value.startswith(query_lower):
                    score *= boost_startswith

            scored_results.append((score, result))

        # Sort by score (descending) and return objects
        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [result for score, result in scored_results]


class ElasticsearchAutocompleteBackend(BaseAutocompleteBackend):
    """
    Elasticsearch-based autocomplete backend.

    This backend uses Elasticsearch for advanced full-text search
    with features like fuzzy matching, relevance scoring, and
    highlighting.

    Requires elasticsearch-dsl or django-elasticsearch-dsl.
    """

    def search(self, queryset: QuerySet, config: Dict[str, Any], view: Any) -> List[Any]:
        """
        Perform Elasticsearch autocomplete search.

        Args:
            queryset: QuerySet (used for model info)
            config: Search configuration
            view: View instance

        Returns:
            List: Search results from Elasticsearch
        """
        try:
            from elasticsearch_dsl import Search, Q as ESQ
        except ImportError:
            logger.error("elasticsearch-dsl not installed. Falling back to database search.")
            return DatabaseAutocompleteBackend().search(queryset, config, view)

        # Check if view has Elasticsearch document
        if not hasattr(view, "document"):
            logger.warning("No Elasticsearch document configured. Falling back to database search.")
            return DatabaseAutocompleteBackend().search(queryset, config, view)

        query = config["query"]
        fields = config["fields"]
        limit = config["limit"]
        fuzzy = config.get("fuzzy", False)

        # Create Elasticsearch search
        search = Search(using=view.document._get_es_connection(), index=view.document._index._name)

        # Build query
        if fuzzy:
            # Fuzzy multi-match query
            es_query = ESQ(
                "multi_match", query=query, fields=fields, fuzziness="AUTO", type="best_fields", tie_breaker=0.3
            )
        else:
            # Standard multi-match query
            es_query = ESQ("multi_match", query=query, fields=fields, type="phrase_prefix")

        # Apply query and limit
        search = search.query(es_query)[:limit]

        # Execute search
        try:
            response = search.execute()

            # Convert Elasticsearch results to model instances
            results = []
            for hit in response:
                # Try to get the actual model instance
                try:
                    instance = queryset.get(pk=hit.meta.id)
                    # Store ES score for potential use
                    instance._es_score = hit.meta.score
                    results.append(instance)
                except queryset.model.DoesNotExist:
                    # Skip if instance doesn't exist in database
                    continue

            return results

        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            # Fallback to database search
            return DatabaseAutocompleteBackend().search(queryset, config, view)


class CacheAutocompleteBackend(BaseAutocompleteBackend):
    """
    Cache-based autocomplete backend.

    This backend pre-computes and caches autocomplete data
    for extremely fast lookups. Suitable for relatively
    static data that doesn't change frequently.
    """

    cache_timeout = 3600  # 1 hour
    cache_key_prefix = "autocomplete_cache"

    def search(self, queryset: QuerySet, config: Dict[str, Any], view: Any) -> List[Any]:
        """
        Perform cache-based autocomplete search.

        Args:
            queryset: Django QuerySet
            config: Search configuration
            view: View instance

        Returns:
            List: Cached search results
        """
        query = config["query"]
        fields = config["fields"]
        limit = config["limit"]

        # Get or build cache
        cache_data = self._get_or_build_cache(queryset, fields, view)

        # Search in cache
        results = self._search_in_cache(cache_data, query, limit, config)

        # Convert IDs back to model instances
        if results:
            result_ids = [r["id"] for r in results]
            instances = queryset.filter(id__in=result_ids)

            # Maintain order from cache results
            id_to_instance = {instance.id: instance for instance in instances}
            ordered_results = []

            for result in results:
                if result["id"] in id_to_instance:
                    instance = id_to_instance[result["id"]]
                    instance._cache_score = result["score"]
                    ordered_results.append(instance)

            return ordered_results

        return []

    def _get_cache_key(self, model_name: str, fields: List[str]) -> str:
        """
        Generate cache key for autocomplete data.

        Args:
            model_name: Model name
            fields: Search fields

        Returns:
            str: Cache key
        """
        fields_hash = hash(tuple(sorted(fields)))
        return f"{self.cache_key_prefix}:{model_name}:{fields_hash}"

    def _get_or_build_cache(self, queryset: QuerySet, fields: List[str], view: Any) -> Dict[str, Any]:
        """
        Get cached data or build it if not exists.

        Args:
            queryset: Django QuerySet
            fields: Search fields
            view: View instance

        Returns:
            Dict: Cached autocomplete data
        """
        model_name = queryset.model._meta.label_lower
        cache_key = self._get_cache_key(model_name, fields)

        # Try to get from cache
        cached_data = cache.get(cache_key)

        if cached_data is None:
            # Build cache data
            cached_data = self._build_cache_data(queryset, fields)

            # Store in cache
            cache.set(cache_key, cached_data, timeout=self.cache_timeout)

            logger.info(f"Built autocomplete cache for {model_name} with {len(cached_data.get('items', []))} items")

        return cached_data

    def _build_cache_data(self, queryset: QuerySet, fields: List[str]) -> Dict[str, Any]:
        """
        Build cache data from queryset.

        Args:
            queryset: Django QuerySet
            fields: Search fields

        Returns:
            Dict: Cache data structure
        """
        items = []

        for instance in queryset.all():
            item = {"id": instance.id, "fields": {}}

            # Store searchable field values
            for field in fields:
                field_value = getattr(instance, field, "")
                item["fields"][field] = str(field_value).lower()

            items.append(item)

        return {"items": items, "fields": fields, "created_at": cache.get("time")}  # For cache invalidation

    def _search_in_cache(
        self, cache_data: Dict[str, Any], query: str, limit: int, config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Search within cached data.

        Args:
            cache_data: Cached autocomplete data
            query: Search query
            limit: Maximum results
            config: Search configuration

        Returns:
            List[Dict]: Search results with scores
        """
        query_lower = query.lower()
        results = []

        boost_exact = config.get("boost_exact", 2.0)
        boost_startswith = config.get("boost_startswith", 1.5)
        fuzzy = config.get("fuzzy", False)
        fuzzy_threshold = config.get("fuzzy_threshold", 0.6)

        for item in cache_data.get("items", []):
            max_score = 0.0

            for field_value in item["fields"].values():
                score = 0.0

                # Exact match
                if field_value == query_lower:
                    score = 1.0 * boost_exact
                # Starts with
                elif field_value.startswith(query_lower):
                    score = 0.8 * boost_startswith
                # Contains
                elif query_lower in field_value:
                    score = 0.6
                # Fuzzy match
                elif fuzzy:
                    similarity = SequenceMatcher(None, query_lower, field_value).ratio()
                    if similarity >= fuzzy_threshold:
                        score = similarity * 0.5

                max_score = max(max_score, score)

            if max_score > 0:
                results.append({"id": item["id"], "score": max_score})

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:limit]

    def invalidate_cache(self, model_name: str, fields: List[str] = None) -> None:
        """
        Invalidate cache for specific model and fields.

        Args:
            model_name: Model name
            fields: Optional specific fields to invalidate
        """
        if fields:
            cache_key = self._get_cache_key(model_name, fields)
            cache.delete(cache_key)
        else:
            # Delete all cache entries for this model
            # This would require a cache backend that supports pattern deletion
            logger.info(f"Cache invalidation requested for model: {model_name}")


class HybridAutocompleteBackend(BaseAutocompleteBackend):
    """
    Hybrid autocomplete backend that combines multiple backends.

    This backend can use different backends for different scenarios:
    - Cache for frequent queries
    - Elasticsearch for complex searches
    - Database for fallback
    """

    def __init__(self):
        self.cache_backend = CacheAutocompleteBackend()
        self.elasticsearch_backend = ElasticsearchAutocompleteBackend()
        self.database_backend = DatabaseAutocompleteBackend()

    def search(self, queryset: QuerySet, config: Dict[str, Any], view: Any) -> List[Any]:
        """
        Perform hybrid autocomplete search.

        Args:
            queryset: Django QuerySet
            config: Search configuration
            view: View instance

        Returns:
            List: Search results from best available backend
        """
        query = config["query"]
        fuzzy = config.get("fuzzy", False)

        # Strategy: Use cache for simple queries, Elasticsearch for complex/fuzzy queries
        if len(query) >= 3 and not fuzzy:
            # Try cache first for simple queries
            try:
                results = self.cache_backend.search(queryset, config, view)
                if results:
                    return results
            except Exception as e:
                logger.debug(f"Cache backend failed: {e}")

        # Try Elasticsearch for complex queries or when cache fails
        if hasattr(view, "document") and (fuzzy or len(query) >= 2):
            try:
                results = self.elasticsearch_backend.search(queryset, config, view)
                if results:
                    return results
            except Exception as e:
                logger.debug(f"Elasticsearch backend failed: {e}")

        # Fallback to database
        return self.database_backend.search(queryset, config, view)
