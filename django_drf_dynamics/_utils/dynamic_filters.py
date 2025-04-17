from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from rest_framework.decorators import action
from rest_framework.response import Response


class DynamicFiltersMixin:
    @classmethod
    def filter_select(cls, title, name, choices_class, is_multiple=False, lookup_expr=None):
        return {
            "title": title,
            "name": name,
            "type": "select_multiple" if is_multiple else "select",
            "data": {"choices": cls.build_select_choices(choices_class), "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_autocomplete(cls, title, name, url):
        return {
            "title": title,
            "name": name,
            "type": "autocomplete",
            "data": {"url": reverse_lazy(url)},
        }

    @classmethod
    def filter_client(cls, title=None, name=None):
        if not title:
            title = _("Client")

        if not name:
            name = "client"

        return cls.filter_autocomplete(title=title, name=name, url="v1:api:clients:bankclient-objects-autocomplete")

    @classmethod
    def filter_client_account(cls, title=None, name=None):
        if not title:
            title = _("Account")

        if not name:
            name = "account"

        return cls.filter_autocomplete(title=title, name=name, url="v1:api:clients:bankaccount-objects-autocomplete")

    @classmethod
    def filter_bool(cls, title, name, lookup_expr=None):
        return {"title": title, "name": name, "type": "bool", "data": {"lookup_expr": lookup_expr}}

    @classmethod
    def filter_form_value(cls, title, name, field_type=None, lookup_expr=None):
        if not field_type:
            field_type = "text"
        return {
            "title": title,
            "name": name,
            "type": "form_value",
            "data": {"field_type": field_type, "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_range(cls, title, name, min_=None, max_=None, step=None, lookup_expr=None):
        if not step:
            step = 1
        return {
            "title": title,
            "name": name,
            "type": "range",
            "data": {"min": min_, "max": max_, "step": step, "lookup_expr": lookup_expr},
        }

    @classmethod
    def filter_datetime_date(cls, title, name, lookup_expr=None):
        return {"title": title, "name": name, "type": "date", "data": {"field_name": name, "lookup_expr": lookup_expr}}

    @classmethod
    def filter_date(cls, title, name, lookup_expr=None):
        return {"title": title, "name": name, "type": "date", "data": {"field_name": name, "lookup_expr": lookup_expr}}

    @classmethod
    def build_select_choices(cls, select_choices):
        choices = [{"title": "All", "value": "", "selected": True}]
        for choice in select_choices:
            choices.append({"title": choice.name, "value": choice.value})

        return choices

    @action(detail=False)
    def objects_filtering_data(self, request):
        """
        Objects filtering data action returns the filters and ordering
        columns data for a given list in a viewset. We must inherit
        ``LookupModelAPIViewMixin`` class in our viewset and configure
        *filterset_metadata*. The filterset_metadata must contain a list of
        dictionaries containing *title*, *name*, *type*, *data*, *range*.

        :var title: must contain the readable title of the filter
        :var name: must contain the filter name that will contain value in the request to backend
        :var type: the filter type (bool, autocomplete, select, date, form_value) to help frontend to render the filter
        :var data: the data dictionary depending on the filter type

        The *bool* and *date* type will contain no data.
        The *autocomplete* type will contain the object related autocomplete link {"url": "/the_autocomplete_url/"}
        The *select* type must contain choices as list of title-value dictionnary {"choices": [{"title": "Status1", "value": "S1"}]}
        The *select_multiple* type must contain choices as list of title-value dictionnary {"choices": [{"title": "Status1", "value": "S1"}]}
        The *form_value* type can contain field_type.
        The *range* type must contain min and max {"min": 0, "max": 100}

        NB: For select, you can use the function *LookupModelAPIViewMixin.build_select_choices* to build object from a models.TextChoices or models.IntegerChoices instance.
        For 'autocomplete' type, use `./manage.py show_urls` with grep to see urls for a specific api and take its url_name. eg: `./manage.py show_urls | grep "clients/list/all"`

        .. hint::
            Example :

            class AccountViewSet():
                queryset = Account.objects.all()
                filterset_metadata = [
                    LookupModelAPIViewMixin.filter_autocomplete(
                        title=_("Client category"),
                        name="client_category",
                        url="v1:api:clients:clientcategory-objects-autocomplete",
                    ),
                    LookupModelAPIViewMixin.filter_autocomplete(
                        title=_("Client type"),
                        name="client_category_type",
                        url="v1:api:clients:clientcategorytype-objects-autocomplete",
                    ),
                    LookupModelAPIViewMixin.filter_autocomplete(
                        title=_("Activity Sector"),
                        name="activity_sector",
                        url="v1:api:clients:activitysector-objects-autocomplete",
                    ),
                    LookupModelAPIViewMixin.filter_client(title=_("Creation client"), name="creation_client"),
                    LookupModelAPIViewMixin.filter_select(
                        title=_("Sex"), name="individual__sex", choices_class=IndividualClientProfile.SexChoice
                    ),
                    LookupModelAPIViewMixin.filter_select(
                        title=_("Marital status"),
                        name="individual__marital_status",
                        choices_class=IndividualClientProfile.MaritalStatusChoice,
                    ),
                    LookupModelAPIViewMixin.filter_bool(title=_("Is secret client ?"), name="client_is_secret"),
                    LookupModelAPIViewMixin.filter_form_value(title=_("Client id"), name="client_id"),
                    LookupModelAPIViewMixin.filter_select(
                        title=_("Prefered language"),
                        name="prefered_language",
                        choices_class=BankClient.ClientLanguages,
                    ),
                ]

        .. warning::
            This configuration will conflict with filterset_fields configuration and custom filter configurations.
            Please be carefull using both of them.
        """
        filterset_metadata = getattr(self, "filterset_metadata", None)
        if not filterset_metadata:
            filterset_metadata = []

            # We populate filterset fields if filterset_metadata is empty
            filterset_fields = getattr(self, "filterset_fields", [])
            for filter_key in filterset_fields:
                filterset_metadata.append(
                    {
                        "title": filter_key.replace("_", " ").capitalize(),
                        "name": filter_key,
                        "type": "form_value",
                        "data": {"field_type": "text"},
                    }
                )

        # We add the created_at filter
        date_filter_details = self.filter_datetime_date(title=_("Creation date"), name="created_at")

        if date_filter_details not in filterset_metadata:
            filterset_metadata.append(date_filter_details)

        if not isinstance(filterset_metadata, (list, tuple)):
            return ImproperlyConfigured(_("Wrong configuration. 'filterset_metadata' must be a dictionnary."))

        filtering_data = {
            "filters": filterset_metadata,
            "ordering": getattr(self, "ordering_fields", None),
        }
        return Response(filtering_data)
