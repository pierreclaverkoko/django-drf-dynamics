import json
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework.filters import BaseFilterBackend

logger = logging.getLogger(__name__)


class JsonFieldFilterBackend(BaseFilterBackend):
    """
    A filter backend for filtering JSON fields with advanced operations.

    Supports operations like:
    - has_key: Check if JSON contains a specific key
    - has_any_keys: Check if JSON contains any of the specified keys
    - has_all_keys: Check if JSON contains all specified keys
    - contains: Check if JSON contains specific key-value pairs
    - contained_by: Check if JSON is contained by the specified JSON

    Example usage:

    ```python
    class ProductViewSet(viewsets.ModelViewSet):
        queryset = Product.objects.all()
        filter_backends = [JsonFieldFilterBackend]
        json_filter_fields = {
            'metadata': {
                'operations': ['has_key', 'contains'],
                'allowed_keys': ['status', 'category', 'tags'],
            }
        }
    ```

    Query parameters:
    - ?metadata_has_key=status
    - ?metadata_contains={"status": "active"}
    - ?metadata_has_any_keys=status,category
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset based on JSON field operations.

        Args:
            request: The HTTP request object
            queryset: The initial queryset
            view: The view instance

        Returns:
            QuerySet: The filtered queryset
        """
        json_filter_fields = getattr(view, "json_filter_fields", {})

        for field_name, field_config in json_filter_fields.items():
            operations = field_config.get("operations", ["has_key", "contains"])
            allowed_keys = field_config.get("allowed_keys", None)

            # Has key operation
            if "has_key" in operations:
                has_key_param = f"{field_name}_has_key"
                key_value = request.query_params.get(has_key_param)
                if key_value:
                    if allowed_keys and key_value not in allowed_keys:
                        continue
                    queryset = queryset.filter(**{f"{field_name}__has_key": key_value})

            # Has any keys operation
            if "has_any_keys" in operations:
                has_any_keys_param = f"{field_name}_has_any_keys"
                keys_value = request.query_params.get(has_any_keys_param)
                if keys_value:
                    keys_list = [k.strip() for k in keys_value.split(",")]
                    if allowed_keys:
                        keys_list = [k for k in keys_list if k in allowed_keys]
                    if keys_list:
                        queryset = queryset.filter(**{f"{field_name}__has_any_keys": keys_list})

            # Has all keys operation
            if "has_all_keys" in operations:
                has_all_keys_param = f"{field_name}_has_all_keys"
                keys_value = request.query_params.get(has_all_keys_param)
                if keys_value:
                    keys_list = [k.strip() for k in keys_value.split(",")]
                    if allowed_keys:
                        keys_list = [k for k in keys_list if k in allowed_keys]
                    if keys_list:
                        queryset = queryset.filter(**{f"{field_name}__has_all_keys": keys_list})

            # Contains operation
            if "contains" in operations:
                contains_param = f"{field_name}_contains"
                contains_value = request.query_params.get(contains_param)
                if contains_value:
                    try:
                        contains_json = json.loads(contains_value)
                        queryset = queryset.filter(**{f"{field_name}__contains": contains_json})
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON for {contains_param}: {contains_value}")

            # Contained by operation
            if "contained_by" in operations:
                contained_by_param = f"{field_name}_contained_by"
                contained_by_value = request.query_params.get(contained_by_param)
                if contained_by_value:
                    try:
                        contained_by_json = json.loads(contained_by_value)
                        queryset = queryset.filter(**{f"{field_name}__contained_by": contained_by_json})
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON for {contained_by_param}: {contained_by_value}")

        return queryset


class NumericOperatorFilterBackend(BaseFilterBackend):
    """
    A filter backend for advanced numeric filtering with multiple operators.

    Supports operations like gt, gte, lt, lte, range, in, not_in.

    Example usage:

    ```python
    class ProductViewSet(viewsets.ModelViewSet):
        queryset = Product.objects.all()
        filter_backends = [NumericOperatorFilterBackend]
        numeric_filter_fields = {
            'price': ['gt', 'gte', 'lt', 'lte', 'range'],
            'rating': ['gte', 'lte'],
            'category_id': ['in', 'not_in'],
        }
    ```

    Query parameters:
    - ?price_gt=100
    - ?price_range=50,200
    - ?category_id_in=1,2,3
    - ?rating_gte=4.0
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset based on numeric operations.

        Args:
            request: The HTTP request object
            queryset: The initial queryset
            view: The view instance

        Returns:
            QuerySet: The filtered queryset
        """
        numeric_filter_fields = getattr(view, "numeric_filter_fields", {})

        for field_name, operations in numeric_filter_fields.items():
            # Greater than
            if "gt" in operations:
                gt_param = f"{field_name}_gt"
                gt_value = request.query_params.get(gt_param)
                if gt_value:
                    try:
                        gt_value = Decimal(gt_value)
                        queryset = queryset.filter(**{f"{field_name}__gt": gt_value})
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Invalid numeric value for {gt_param}: {gt_value}")

            # Greater than or equal
            if "gte" in operations:
                gte_param = f"{field_name}_gte"
                gte_value = request.query_params.get(gte_param)
                if gte_value:
                    try:
                        gte_value = Decimal(gte_value)
                        queryset = queryset.filter(**{f"{field_name}__gte": gte_value})
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Invalid numeric value for {gte_param}: {gte_value}")

            # Less than
            if "lt" in operations:
                lt_param = f"{field_name}_lt"
                lt_value = request.query_params.get(lt_param)
                if lt_value:
                    try:
                        lt_value = Decimal(lt_value)
                        queryset = queryset.filter(**{f"{field_name}__lt": lt_value})
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Invalid numeric value for {lt_param}: {lt_value}")

            # Less than or equal
            if "lte" in operations:
                lte_param = f"{field_name}_lte"
                lte_value = request.query_params.get(lte_param)
                if lte_value:
                    try:
                        lte_value = Decimal(lte_value)
                        queryset = queryset.filter(**{f"{field_name}__lte": lte_value})
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Invalid numeric value for {lte_param}: {lte_value}")

            # Range
            if "range" in operations:
                range_param = f"{field_name}_range"
                range_value = request.query_params.get(range_param)
                if range_value:
                    try:
                        range_parts = [Decimal(part.strip()) for part in range_value.split(",")]
                        if len(range_parts) == 2:
                            queryset = queryset.filter(**{f"{field_name}__range": range_parts})
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Invalid range value for {range_param}: {range_value}")

            # In
            if "in" in operations:
                in_param = f"{field_name}_in"
                in_value = request.query_params.get(in_param)
                if in_value:
                    try:
                        in_list = [part.strip() for part in in_value.split(",")]
                        # Try to convert to numbers if possible
                        try:
                            in_list = [Decimal(val) for val in in_list]
                        except (ValueError, InvalidOperation):
                            # Keep as strings if conversion fails
                            pass
                        queryset = queryset.filter(**{f"{field_name}__in": in_list})
                    except Exception as e:
                        logger.warning(f"Invalid in value for {in_param}: {in_value}, error: {e}")

            # Not in
            if "not_in" in operations:
                not_in_param = f"{field_name}_not_in"
                not_in_value = request.query_params.get(not_in_param)
                if not_in_value:
                    try:
                        not_in_list = [part.strip() for part in not_in_value.split(",")]
                        # Try to convert to numbers if possible
                        try:
                            not_in_list = [Decimal(val) for val in not_in_list]
                        except (ValueError, InvalidOperation):
                            # Keep as strings if conversion fails
                            pass
                        queryset = queryset.exclude(**{f"{field_name}__in": not_in_list})
                    except Exception as e:
                        logger.warning(f"Invalid not_in value for {not_in_param}: {not_in_value}, error: {e}")

        return queryset


class TextSearchFilterBackend(BaseFilterBackend):
    """
    A filter backend for advanced text search with multiple search types.

    Supports search types like icontains, iexact, istartswith, iendswith, regex, iregex.
    Also supports multi-field search.

    Example usage:

    ```python
    class ProductViewSet(viewsets.ModelViewSet):
        queryset = Product.objects.all()
        filter_backends = [TextSearchFilterBackend]
        text_search_fields = {
            'name': ['icontains', 'istartswith'],
            'description': ['icontains'],
            'global_search': {
                'fields': ['name', 'description', 'category__name'],
                'search_type': 'icontains'
            }
        }
    ```

    Query parameters:
    - ?name_icontains=phone
    - ?name_istartswith=smart
    - ?global_search=smartphone
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset based on text search operations.

        Args:
            request: The HTTP request object
            queryset: The initial queryset
            view: The view instance

        Returns:
            QuerySet: The filtered queryset
        """
        text_search_fields = getattr(view, "text_search_fields", {})

        for field_name, field_config in text_search_fields.items():
            if isinstance(field_config, dict):
                # Multi-field search
                search_param = field_name
                search_value = request.query_params.get(search_param)
                if search_value:
                    fields = field_config.get("fields", [field_name])
                    search_type = field_config.get("search_type", "icontains")

                    search_q = Q()
                    for field in fields:
                        search_q |= Q(**{f"{field}__{search_type}": search_value})

                    queryset = queryset.filter(search_q)

            elif isinstance(field_config, list):
                # Single field with multiple search types
                for search_type in field_config:
                    search_param = f"{field_name}_{search_type}"
                    search_value = request.query_params.get(search_param)
                    if search_value:
                        queryset = queryset.filter(**{f"{field_name}__{search_type}": search_value})

        return queryset


class GeographicFilterBackend(BaseFilterBackend):
    """
    A filter backend for geographic filtering operations.

    Requires django.contrib.gis (GeoDjango) to be installed and configured.

    Supports operations like:
    - distance: Find objects within a certain distance of a point
    - distance_gte/lte: Find objects greater/less than a distance from a point
    - bbcontains: Find objects within a bounding box
    - intersects: Find objects that intersect with a geometry

    Example usage:

    ```python
    class StoreViewSet(viewsets.ModelViewSet):
        queryset = Store.objects.all()
        filter_backends = [GeographicFilterBackend]
        geographic_filter_fields = {
            'location': ['distance', 'distance_lte'],
        }
    ```

    Query parameters:
    - ?location_distance=40.7128,-74.0060,5km
    - ?location_distance_lte=40.7128,-74.0060,10mi
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset based on geographic operations.

        Args:
            request: The HTTP request object
            queryset: The initial queryset
            view: The view instance

        Returns:
            QuerySet: The filtered queryset
        """
        try:
            from django.contrib.gis.geos import Point
            from django.contrib.gis.measure import D
        except ImportError:
            logger.warning("GeoDjango is not installed. Geographic filtering is not available.")
            return queryset

        geographic_filter_fields = getattr(view, "geographic_filter_fields", {})

        for field_name, operations in geographic_filter_fields.items():
            # Distance operations
            for operation in operations:
                if operation.startswith("distance"):
                    param_name = f"{field_name}_{operation}"
                    param_value = request.query_params.get(param_name)

                    if param_value:
                        try:
                            # Parse parameter: "lat,lon,distance_unit"
                            # Example: "40.7128,-74.0060,5km"
                            parts = param_value.split(",")
                            if len(parts) >= 3:
                                lat = float(parts[0])
                                lon = float(parts[1])
                                distance_str = parts[2]

                                # Parse distance with unit
                                distance_value = float("".join(filter(str.isdigit, distance_str.replace(".", ""))))
                                distance_unit = "".join(filter(str.isalpha, distance_str))

                                point = Point(lon, lat, srid=4326)
                                distance = D(**{distance_unit or "km": distance_value})

                                if operation == "distance":
                                    queryset = queryset.filter(**{f"{field_name}__distance_lte": (point, distance)})
                                elif operation == "distance_lte":
                                    queryset = queryset.filter(**{f"{field_name}__distance_lte": (point, distance)})
                                elif operation == "distance_gte":
                                    queryset = queryset.filter(**{f"{field_name}__distance_gte": (point, distance)})
                                elif operation == "distance_gt":
                                    queryset = queryset.filter(**{f"{field_name}__distance_gt": (point, distance)})
                                elif operation == "distance_lt":
                                    queryset = queryset.filter(**{f"{field_name}__distance_lt": (point, distance)})

                        except (ValueError, IndexError, TypeError) as e:
                            logger.warning(f"Invalid geographic parameter {param_name}: {param_value}, error: {e}")

        return queryset


class CustomValidationFilterBackend(BaseFilterBackend):
    """
    A filter backend that allows custom validation of filter parameters.

    Example usage:

    ```python
    class ProductViewSet(viewsets.ModelViewSet):
        queryset = Product.objects.all()
        filter_backends = [CustomValidationFilterBackend]

        def validate_price_filter(self, value):
            try:
                price = float(value)
                if price < 0:
                    raise ValidationError("Price must be positive")
                return price
            except ValueError:
                raise ValidationError("Invalid price format")

        def validate_category_filter(self, value):
            valid_categories = ['electronics', 'books', 'clothing']
            if value not in valid_categories:
                raise ValidationError(f"Category must be one of: {valid_categories}")
            return value

        custom_filter_validators = {
            'price': 'validate_price_filter',
            'category': 'validate_category_filter',
        }
    ```
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset with custom validation.

        Args:
            request: The HTTP request object
            queryset: The initial queryset
            view: The view instance

        Returns:
            QuerySet: The filtered queryset
        """
        custom_filter_validators = getattr(view, "custom_filter_validators", {})

        for filter_name, validator_method_name in custom_filter_validators.items():
            param_value = request.query_params.get(filter_name)

            if param_value:
                validator_method = getattr(view, validator_method_name, None)

                if validator_method and callable(validator_method):
                    try:
                        validated_value = validator_method(param_value)
                        queryset = queryset.filter(**{filter_name: validated_value})
                    except ValidationError as e:
                        logger.warning(f"Validation error for {filter_name}: {e}")
                        # You might want to raise the error or handle it differently
                        # based on your requirements
                else:
                    logger.warning(f"Validator method {validator_method_name} not found in view")

        return queryset
