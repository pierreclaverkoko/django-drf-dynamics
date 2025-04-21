import datetime
import decimal
import json

from rest_framework.renderers import JSONRenderer


class JSONEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that handles additional data types.

    This encoder extends the default `json.JSONEncoder` to support encoding
    complex numbers, decimals, dates, and objects with a custom `get_drf_dynamic_json` method.
    It also ensures that strings are encoded in UTF-8, ignoring non-UTF characters.

    Methods:
        default(obj): Encodes custom object types into JSON-serializable formats.
    """

    def default(self, obj):
        """
        Encode custom object types into JSON-serializable formats.

        Args:
            obj: The object to encode.

        Returns:
            A JSON-serializable representation of the object.

        Raises:
            TypeError: If the object cannot be serialized.
        """
        if hasattr(obj, "get_drf_dynamic_json"):
            # Call the custom method if it exists
            json_func = getattr(obj, "get_drf_dynamic_json", None)
            if json_func:
                return json_func()
        elif isinstance(obj, complex):
            # Encode complex numbers as a list of [real, imaginary]
            return [obj.real, obj.imag]
        elif isinstance(obj, decimal.Decimal):
            # Convert decimals to strings
            return str(obj)
        elif isinstance(obj, (datetime.date, datetime.datetime)):
            # Convert dates and datetimes to ISO format
            return obj.isoformat()
        elif isinstance(obj, str):
            # Encode strings in UTF-8, ignoring non-UTF characters
            return bytes(obj, "utf-8").decode("utf-8", "ignore")
        elif not isinstance(obj, str):
            # Convert other non-string objects to strings
            return str(obj)

        # Let the base class handle unsupported types
        return super().default(obj)


class ApiRenderer(JSONRenderer):
    """
    A custom renderer for API responses.

    This renderer extends the default `JSONRenderer` to provide custom formatting
    for paginated responses and other API data. It uses the `JSONEncoder` class
    for encoding data into JSON.

    Attributes:
        charset (str): The character set used for encoding. Defaults to "utf-8".
        object_label (str): The label for single objects in the response. Defaults to "object".
        pagination_object_label (str): The label for paginated objects. Defaults to "objects".
        pagination_object_count (str): The label for the count of paginated objects. Defaults to "count".
        pagination_count_label (str): Alias for `pagination_object_count`.
        pagination_next_page_label (str): The label for the next page URL. Defaults to "next_page".
        pagination_previous_page_label (str): The label for the previous page URL. Defaults to "prev_page".

    Methods:
        render(data, media_type=None, renderer_context=None): Renders the API response data into JSON format.
    """

    charset = "utf-8"
    object_label = "object"
    pagination_object_label = "objects"
    pagination_object_count = "count"
    pagination_count_label = pagination_object_count  # To solve a bug
    pagination_next_page_label = "next_page"
    pagination_previous_page_label = "prev_page"

    def render(self, data, media_type=None, renderer_context=None):
        """
        Render the API response data into JSON format.

        This method customizes the rendering of paginated responses and handles
        cases where the response contains errors or facets.

        Args:
            data (dict): The data to render.
            media_type (str, optional): The media type of the response. Defaults to None.
            renderer_context (dict, optional): Additional context for rendering. Defaults to None.

        Returns:
            str: The rendered JSON string.
        """
        if getattr(data, "get", None):
            if data.get("results", None) is not None:
                # Handle paginated responses
                results_return_data = {
                    self.pagination_object_label: data["results"],
                    self.pagination_count_label: data["count"],
                    self.pagination_next_page_label: data["next"],
                    self.pagination_previous_page_label: data["previous"],
                }
                if data.get("facets", None) is not None:
                    # Include facets if present
                    results_return_data["facets"] = data["facets"]

                return json.dumps(results_return_data, cls=JSONEncoder)

            elif data.get("errors", None) is not None:
                # Let the default JSONRenderer handle errors
                return super().render(data)

        # Handle non-paginated responses
        return json.dumps({self.object_label: data}, cls=JSONEncoder)
