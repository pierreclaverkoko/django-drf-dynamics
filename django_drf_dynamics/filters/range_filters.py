import decimal

from django.db.models import Q
from rest_framework.filters import BaseFilterBackend


class AmountFilterBackend(BaseFilterBackend):
    """
    A filter backend that filters the queryset by amount range.

    This filter backend allows filtering querysets based on multiple amount ranges
    provided in the query parameters. Each range is defined as a field name followed
    by a colon and a range definition (e.g., `field_name:min-max`). Multiple ranges
    can be separated by commas.

    Example usage:

    ```python
    # Query parameter example:
    # ?amount_ranges=trans_amount:34000-450000,trans_commissions:23000-4599999

    class ExampleViewSet(viewsets.ModelViewSet):
        queryset = Transaction.objects.all()
        filter_backends = [AmountFilterBackend]
    ```

    Attributes:
        None
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset based on the amount ranges provided in the query parameters.

        Args:
            request: The HTTP request object containing query parameters.
            queryset: The initial queryset to be filtered.
            view: The view instance calling this filter backend.

        Returns:
            QuerySet: The filtered queryset.

        Example query parameter:
            ?amount_ranges=trans_amount:34000-450000,trans_commissions:23000-4599999

        Raises:
            ValueError: If the range values cannot be converted to decimals.
        """
        # Get the amount range from the request
        # eg: trans_amount:34000-450000,trans_commissions:23000-4599999
        amount_ranges_all = request.query_params.get("amount_ranges", None)
        amount_ranges_dict = {}

        if not amount_ranges_all:
            return queryset

        # We split ranges elements using ","
        amount_ranges_split = amount_ranges_all.split(",")
        for amount_range in amount_ranges_split:
            amount_range = amount_range.strip()

            # We split the field name from the final range
            amount_range_elements = amount_range.split(":")

            # We split the final range using "-"
            amount_range_element_split = amount_range_elements[1].split("-")
            amount_range_element_split_len = len(amount_range_element_split)
            if amount_range_element_split_len > 2 or amount_range_element_split_len <= 0:
                # We don't use the empty or excessive range
                continue

            # We will use None to exclude the higher comparison
            if amount_range_element_split_len == 1:
                amount_range_element_split.append(None)

            amount_ranges_dict[amount_range_elements[0].strip()] = amount_range_element_split

        if not amount_ranges_dict:
            return queryset

        amount_filter_q = Q()

        for amount_field, amount_list in amount_ranges_dict.items():
            amount_low = amount_list[0]
            amount_high = amount_list[1]

            # Convert the value to Decimal objects
            try:
                amount_low = decimal.Decimal(amount_low)
                if amount_high:
                    amount_high = decimal.Decimal(amount_high)
            except (ValueError, decimal.InvalidOperation):
                continue

            amount_filter_q = Q(**{f"{amount_field}__gte": amount_low})
            if amount_high:
                amount_filter_q = amount_filter_q & Q(**{f"{amount_field}__lte": amount_high})

        # Apply the filter to the queryset and return it
        return queryset.filter(amount_filter_q)
