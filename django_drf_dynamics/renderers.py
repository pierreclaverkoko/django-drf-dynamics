import datetime
import decimal
import json

from rest_framework.renderers import JSONRenderer


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        """This function encodes several objects types to readable json data types"""
        if hasattr(obj, "get_drf_dynamic_json"):
            # This is to help models and other objects that has the
            # function 'get_drf_dynamic_json' to be called
            json_func = getattr(obj, "get_drf_dynamic_json", None)
            if json_func:
                return json_func()
        elif isinstance(obj, complex):
            return [obj.real, obj.imag]
        elif isinstance(obj, decimal.Decimal):
            return str(obj)
        elif isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        elif isinstance(obj, str):
            # This ignores all non utf chars in the JSON
            # It helps then to avoid some conflicts with partners systems
            return bytes(obj, "utf-8").decode("utf-8", "ignore")
        elif not isinstance(obj, str):
            return str(obj)

        # Let the base class default method raise the TypeError
        return super().default(obj)


class ApiRenderer(JSONRenderer):
    charset = "utf-8"
    object_label = "object"
    pagination_object_label = "objects"
    pagination_object_count = "count"
    pagination_count_label = pagination_object_count  # To solve a bug
    pagination_next_page_label = "next_page"
    pagination_previous_page_label = "prev_page"

    def render(self, data, media_type=None, renderer_context=None):
        """The default render for the renderer"""
        if getattr(data, "get", None):
            if data.get("results", None) is not None:
                results_return_data = {
                    self.pagination_object_label: data["results"],
                    self.pagination_count_label: data["count"],
                    self.pagination_next_page_label: data["next"],
                    self.pagination_previous_page_label: data["previous"],
                }
                if data.get("facets", None) is not None:
                    results_return_data["facets"] = data["facets"]

                return json.dumps(results_return_data, cls=JSONEncoder)

            # If the view throws an error (such as the user can't be authenticated
            # or something similar), `data` will contain an `errors` key. We want
            # the default JSONRenderer to handle rendering errors, so we need to
            # check for this case.
            elif data.get("errors", None) is not None:
                return super().render(data)

        return json.dumps({self.object_label: data}, cls=JSONEncoder)
