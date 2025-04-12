from django.db.models import Q
from django.utils import timezone
from rest_framework.filters import BaseFilterBackend


class DateFilterBackend(BaseFilterBackend):
    """A filter backend that filters the queryset by date range.

    OLD FASHION STYLE :
    It expects the request to have 'date_from' and 'date_to' query
    parameters, which are ISO-formatted date strings, such as
    '2023-11-27'. It also expects the view to have a 'date_field'
    attribute, which is the name of the model field to filter by, such
    as 'created_at'. Alternatively, you can send a query_params named
    'custom_date_field' to be used as date field for queryset.

    NEW FASHION STYLE :
    It expects the request to have 'date_ranges' query parameter, which has a list of date rangers members.
    Each member must contain the field name, the from date and probably the to date.
    Here is a filter example for 3 date fields
    Eg : ?date_ranges=created_at__date:2023-01-12:2023-02-23,birthday:1994-09-12:1995-03-25,issue_date:2024-05-01
    """

    def filter_queryset(self, request, queryset, view):
        # Get the date range from the request
        date_from = request.query_params.get("date_from", None)
        date_to = request.query_params.get("date_to", None)
        custom_date_field = request.query_params.get("custom_date_field", None)
        # New range field
        date_ranges_all = request.query_params.get("date_ranges", None)

        # DEPRECATED OLD LOGIC : HERE FOR COMPATIBILITY
        if date_from:
            # Get the date field from the view
            date_field = getattr(view, "date_field", custom_date_field)

            # Validate the inputs
            if not date_field:
                # raise AttributeError("The view must have a date_field attribute.")
                date_field = "created_at__date"

            # Convert the date strings to date objects
            try:
                date_from = timezone.datetime.fromisoformat(date_from).date()
                if date_to:
                    date_to = timezone.datetime.fromisoformat(date_to).date()
            except ValueError:
                return queryset

            # Construct the date range filter
            date_filter = Q(**{f"{date_field}__gte": date_from})

            if date_to:
                date_filter = date_filter & Q(**{f"{date_field}__lte": date_to})

            # Apply the filter to the queryset and return it
            return queryset.filter(date_filter)
        else:
            if not date_ranges_all:
                return queryset

            # We split ranges elements using ","
            date_ranges_split = date_ranges_all.split(",")
            date_ranges_dict = {}

            for date_range in date_ranges_split:
                date_range = date_range.strip()

                # We split the field name from the final range
                date_range_elements = date_range.split(":")
                date_range_element_len = len(date_range_elements)
                date_range_split = []
                if date_range_element_len > 3 or date_range_element_len <= 1:
                    # We don't use the empty or excessive range
                    continue
                elif date_range_element_len == 2:
                    date_range_split = [date_range_elements[1].strip()]
                elif date_range_element_len == 3:
                    date_range_split = [date_range_elements[1].strip(), date_range_elements[2].strip()]

                date_ranges_dict[date_range_elements[0].strip()] = date_range_split

            date_filter_q = Q()

            for date_field, date_list in date_ranges_dict.items():
                date_low = date_list[0]
                date_high = date_list[1]

                # Convert the value to Decimal objects
                try:
                    date_low = timezone.datetime.fromisoformat(date_low).date()
                    if date_high:
                        date_high = timezone.datetime.fromisoformat(date_high).date()
                except ValueError:
                    continue

                date_filter_q = Q(**{f"{date_field}__gte": date_low})
                if date_high:
                    date_filter_q = date_filter_q & Q(**{f"{date_field}__lte": date_high})

            # Apply the filter to the queryset and return it
            return queryset.filter(date_filter_q)
