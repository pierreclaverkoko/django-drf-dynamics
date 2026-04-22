"""Unit tests for composite cell helpers and :class:`~django_drf_dynamics.serializers.CompositeCellField`."""

from __future__ import annotations

import unittest

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django_drf_dynamics.serializers.composite_cell import (
    AMOUNT_COMPOSITE_KIND,
    COMPOSITE_CELL_KIND,
    COMPOSITE_LAYOUT_MEDIA_TWO_LINE,
    STACKED_CELL_KIND,
    AmountCompositeField,
    CompositeCellField,
    StackedCellField,
    resolve_dotted_path,
    validate_amount_composite,
    validate_composite_cell,
    validate_stacked_cell,
)


class ResolveDottedPathTests(unittest.TestCase):
    def test_simple_attribute(self) -> None:
        class O:
            x = 1

        self.assertEqual(resolve_dotted_path(O(), "x"), 1)

    def test_nested_mapping(self) -> None:
        d = {"a": {"b": 2}}
        self.assertEqual(resolve_dotted_path(d, "a.b"), 2)

    def test_none_path(self) -> None:
        self.assertIsNone(resolve_dotted_path(object(), None))


class ValidateCompositeCellTests(unittest.TestCase):
    def test_valid_media_two_line(self) -> None:
        out = validate_composite_cell(
            {
                "kind": COMPOSITE_CELL_KIND,
                "layout": COMPOSITE_LAYOUT_MEDIA_TWO_LINE,
                "primary": "Name",
                "secondary": "CODE",
            }
        )
        self.assertEqual(out["primary"], "Name")
        self.assertEqual(out["secondary"], "CODE")

    def test_rejects_wrong_kind(self) -> None:
        with self.assertRaises(ValidationError):
            validate_composite_cell(
                {"kind": "x", "layout": COMPOSITE_LAYOUT_MEDIA_TWO_LINE, "primary": "A"}
            )

    def test_accepts_empty_primary_for_media_two_line(self) -> None:
        out = validate_composite_cell(
            {"kind": COMPOSITE_CELL_KIND, "layout": COMPOSITE_LAYOUT_MEDIA_TWO_LINE, "primary": ""}
        )
        self.assertEqual(out["primary"], "")
        self.assertNotIn("secondary", out)


class CompositeCellFieldTests(unittest.TestCase):
    def test_declarative_build(self) -> None:
        class FE:
            name = "Prov"
            code = "PC"

        class Row:
            financial_entity = FE()

        class S(serializers.Serializer):
            provider = CompositeCellField(
                layout=COMPOSITE_LAYOUT_MEDIA_TWO_LINE,
                primary_path="financial_entity.name",
                secondary_path="financial_entity.code",
            )

        s = S(instance=Row())
        data = s.data
        self.assertEqual(data["provider"]["primary"], "Prov")
        self.assertEqual(data["provider"]["secondary"], "PC")

    def test_method_mode(self) -> None:
        class Row:
            pass

        class S(serializers.Serializer):
            cell = CompositeCellField()

            def get_cell(self, obj: object) -> dict:
                return {
                    "kind": COMPOSITE_CELL_KIND,
                    "layout": COMPOSITE_LAYOUT_MEDIA_TWO_LINE,
                    "primary": "P",
                }

        s = S(instance=Row())
        self.assertEqual(s.data["cell"]["primary"], "P")


class ValidateStackedCellTests(unittest.TestCase):
    def test_valid_stacked_cell(self) -> None:
        out = validate_stacked_cell(
            {
                "kind": STACKED_CELL_KIND,
                "top": "Internal Ref",
                "bottom": "External Ref",
            }
        )
        self.assertEqual(out["top"], "Internal Ref")
        self.assertEqual(out["bottom"], "External Ref")

    def test_accepts_when_both_lines_empty(self) -> None:
        out = validate_stacked_cell({"kind": STACKED_CELL_KIND, "top": "", "bottom": ""})
        self.assertEqual(out["top"], "")
        self.assertEqual(out["bottom"], "")


class ValidateAmountCompositeTests(unittest.TestCase):
    def test_valid_amount_composite(self) -> None:
        out = validate_amount_composite(
            {
                "kind": AMOUNT_COMPOSITE_KIND,
                "amount": "1250.50",
                "currency": "usd",
            }
        )
        self.assertEqual(out["amount"], "1250.50")
        self.assertEqual(out["currency"], "USD")

    def test_rejects_missing_currency(self) -> None:
        with self.assertRaises(ValidationError):
            validate_amount_composite(
                {"kind": AMOUNT_COMPOSITE_KIND, "amount": "10", "currency": ""}
            )


class StackedCellFieldTests(unittest.TestCase):
    def test_declarative_build(self) -> None:
        class Row:
            internal_reference = "INT-001"
            external_reference = "EXT-001"

        class S(serializers.Serializer):
            refs = StackedCellField(
                top_path="internal_reference",
                bottom_path="external_reference",
            )

        s = S(instance=Row())
        self.assertEqual(s.data["refs"]["kind"], STACKED_CELL_KIND)
        self.assertEqual(s.data["refs"]["top"], "INT-001")
        self.assertEqual(s.data["refs"]["bottom"], "EXT-001")


class AmountCompositeFieldTests(unittest.TestCase):
    def test_declarative_build(self) -> None:
        class C:
            code = "BIF"

        class Row:
            amount = "5500.00"
            currency = C()

        class S(serializers.Serializer):
            amount_display = AmountCompositeField(
                amount_path="amount",
                currency_path="currency.code",
            )

        s = S(instance=Row())
        self.assertEqual(s.data["amount_display"]["kind"], AMOUNT_COMPOSITE_KIND)
        self.assertEqual(s.data["amount_display"]["amount"], "5500.00")
        self.assertEqual(s.data["amount_display"]["currency"], "BIF")
