"""The ``fields`` query param of advanced autocomplete must never widen the configured search fields."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from django_drf_dynamics.autocomplete.advanced_autocomplete import (
    AdvancedAutocompleteMixin,
    CachedAutocompleteMixin,
)


class _View(AdvancedAutocompleteMixin):
    autocomplete_fields = ["email", "username"]


def _request(fields: str | None) -> SimpleNamespace:
    params = {} if fields is None else {"fields": fields}
    return SimpleNamespace(query_params=params)


class RequestedSearchFieldsTests(unittest.TestCase):
    def test_defaults_to_configured_fields(self) -> None:
        self.assertEqual(_View().get_requested_search_fields(_request(None)), ["email", "username"])

    def test_can_narrow_to_a_configured_field(self) -> None:
        self.assertEqual(_View().get_requested_search_fields(_request("username")), ["username"])

    def test_unconfigured_fields_are_dropped(self) -> None:
        got = _View().get_requested_search_fields(_request("email, password ,user_roles__user__password"))
        self.assertEqual(got, ["email"])

    def test_only_unconfigured_fields_fall_back_to_configured(self) -> None:
        got = _View().get_requested_search_fields(_request("password,api_keys__secret_hash"))
        self.assertEqual(got, ["email", "username"])

    def test_empty_param_falls_back(self) -> None:
        self.assertEqual(_View().get_requested_search_fields(_request(" , ")), ["email", "username"])

    def test_cached_mixin_inherits_the_guard(self) -> None:
        self.assertIs(
            CachedAutocompleteMixin.get_requested_search_fields, AdvancedAutocompleteMixin.get_requested_search_fields
        )
