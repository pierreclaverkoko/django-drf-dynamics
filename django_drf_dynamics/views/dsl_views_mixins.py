from django_elasticsearch_dsl_drf import filter_backends as dsl_filter_backends
from django_elasticsearch_dsl_drf.pagination import LimitOffsetPagination as DslLimitOffsetPagination
from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet


class ElasticDslViewSet(DocumentViewSet):
    """
    Base viewset for Elasticsearch DSL integration with Django REST Framework.

    This viewset provides default configurations for integrating Elasticsearch
    with DRF, including pagination, filtering, and ordering. It is designed to
    be extended by child viewsets that define specific configurations such as
    `document`, `serializer_class`, and additional filter fields.

    Attributes:
        lookup_field (str): The field used to look up objects. Defaults to "id".
        pagination_class (class): The pagination class used for limiting and
            offsetting results. Defaults to `DslLimitOffsetPagination`.
        filter_backends (list): A list of filter backends for Elasticsearch DSL.
            Includes ordering, default ordering, compound search, faceted search,
            filtering, post-filtering, and ID-based filtering.
        ordering (tuple): Default ordering for query results. Defaults to ("id", "created_at").
        ordering_fields (dict): Fields available for ordering. Maps field names
            to their corresponding Elasticsearch fields.
        faceted_search_fields (dict): Fields for faceted search. Should be defined
            in child viewsets. Example structure is provided in comments.
        filter_fields (dict): Fields for filtering. Should be defined in child viewsets.
        post_filter_fields (dict): Fields for post-filtering. Should be defined in child viewsets.
    """

    lookup_field = "id"
    pagination_class = DslLimitOffsetPagination
    filter_backends = [
        dsl_filter_backends.OrderingFilterBackend,
        dsl_filter_backends.DefaultOrderingFilterBackend,
        dsl_filter_backends.CompoundSearchFilterBackend,
        dsl_filter_backends.FacetedSearchFilterBackend,
        dsl_filter_backends.FilteringFilterBackend,
        dsl_filter_backends.PostFilterFilteringFilterBackend,
        dsl_filter_backends.IdsFilterBackend,
        dsl_filter_backends.OrderingFilterBackend,
    ]
    ordering = ("id", "created_at")
    ordering_fields = {"created_at": "created_at", "id": "id"}

    faceted_search_fields = {
        # Define this in the child viewset
        # Example:
        # 'state_global': {
        #     'field': 'state.raw',
        #     'enabled': True,
        #     'global': True,  # This makes the aggregation global
        # },
    }
    filter_fields = {}  # Define this in the child viewset
    post_filter_fields = {}  # Define this in the child viewset
