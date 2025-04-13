import decimal

from django.db.models import Q
from rest_framework.filters import BaseFilterBackend


class AmountFilterBackend(BaseFilterBackend):
    """A filter backend that filters the queryset by amount range.

    Here is an example of filter :
    eg: trans_amount:34000-450000,trans_commissions:23000-4599999
    Every range definition has two members separated by ":".
    The first member contains the field to be queried and the second
    member contains the range definition.
    We can then send many ranges.
    """

    def filter_queryset(self, request, queryset, view):
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

            # We will use None to exclude le higher comparison
            if amount_range_element_split_len == 1:
                amount_range_element_split[1] = None

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
