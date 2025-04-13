from django_elasticsearch_dsl_drf import filter_backends as dsl_filter_backends
from django_elasticsearch_dsl_drf.pagination import LimitOffsetPagination as DslLimitOffsetPagination
from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet


class ElasticDslViewSet(DocumentViewSet):
    """
    Base viewset for Elastic search dsl for django rest framework
    Mandatory fields :

    * document
    * serializer_class
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

    faceted_search_fields = {  # Define this in the child viewset
        # 'state_global': {
        #     'field': 'state.raw',
        #     'enabled': True,
        #     'global': True,  # This makes the aggregation global
        # },
    }
    filter_fields = {}  # Define this in the child viewset
    post_filter_fields = {}  # Define this in the child viewset
