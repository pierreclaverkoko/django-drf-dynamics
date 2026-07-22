"""Unit tests for writable ChoiceEnumField and dynamic form metadata."""

from __future__ import annotations

import unittest

from django.db import models
from rest_framework import serializers

from django_drf_dynamics._utils.dynamic_forms import DynamicFormsMixin
from django_drf_dynamics.serializers.fields import ChoiceEnumField


class _StatusModel(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FAILED = "FAILED", "Failed"

    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        app_label = "drf_dynamics_tests"

    def get_status_css(self) -> str:
        if self.status == self.Status.ACTIVE:
            return "success"
        if self.status == self.Status.FAILED:
            return "danger"
        return "default"


class ChoiceEnumFieldTests(unittest.TestCase):
    def test_to_representation_returns_rich_object(self) -> None:
        class S(serializers.ModelSerializer):
            status = ChoiceEnumField()

            class Meta:
                model = _StatusModel
                fields = ["status"]

        obj = _StatusModel(status=_StatusModel.Status.ACTIVE)
        data = S(obj).data
        self.assertEqual(
            data["status"],
            {"value": "ACTIVE", "title": "Active", "css": "success"},
        )

    def test_to_internal_accepts_raw_value(self) -> None:
        class S(serializers.ModelSerializer):
            status = ChoiceEnumField()

            class Meta:
                model = _StatusModel
                fields = ["status"]

        ser = S(data={"status": "FAILED"})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["status"], "FAILED")

    def test_to_internal_accepts_rich_object(self) -> None:
        class S(serializers.ModelSerializer):
            status = ChoiceEnumField()

            class Meta:
                model = _StatusModel
                fields = ["status"]

        ser = S(data={"status": {"value": "ACTIVE", "title": "Active", "css": "success"}})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["status"], "ACTIVE")

    def test_display_alias_is_read_only(self) -> None:
        class S(serializers.ModelSerializer):
            status_display = ChoiceEnumField(choice_field_name="status")

            class Meta:
                model = _StatusModel
                fields = ["status", "status_display"]

        field = S().fields["status_display"]
        self.assertTrue(field.read_only)

    def test_rejects_invalid_choice(self) -> None:
        class S(serializers.ModelSerializer):
            status = ChoiceEnumField()

            class Meta:
                model = _StatusModel
                fields = ["status"]

        ser = S(data={"status": "NOPE"})
        self.assertFalse(ser.is_valid())
        self.assertIn("status", ser.errors)


class DynamicFormsChoiceEnumAndJsonTests(unittest.TestCase):
    def test_choiceenum_emitted_as_select_with_choices(self) -> None:
        class S(serializers.ModelSerializer):
            status = ChoiceEnumField()

            class Meta:
                model = _StatusModel
                fields = ["status"]

        class View(DynamicFormsMixin):
            pass

        form = View().get_dynamic_form_fields(S)
        self.assertIn("status", form)
        self.assertEqual(form["status"]["html_type"], "select")
        self.assertEqual(form["status"]["type"], "choiceenumfield")
        values = {c["value"] for c in form["status"]["choices"]}
        self.assertEqual(values, {"ACTIVE", "FAILED"})

    def test_jsonfield_has_key_value_editor(self) -> None:
        class CfgModel(models.Model):
            configuration = models.JSONField(default=dict, blank=True)

            class Meta:
                app_label = "drf_dynamics_tests"

        class S(serializers.ModelSerializer):
            class Meta:
                model = CfgModel
                fields = ["configuration"]

        class View(DynamicFormsMixin):
            pass

        form = View().get_dynamic_form_fields(S)
        self.assertEqual(form["configuration"]["html_type"], "json")
        self.assertEqual(form["configuration"]["editor"], "key_value_json")




class DynamicFormsRequiredAndFileTests(unittest.TestCase):
    def test_optional_null_fields_not_required(self) -> None:
        class OptModel(models.Model):
            name = models.CharField(max_length=50, blank=True, null=True)
            logo = models.ImageField(upload_to="x/", blank=True, null=True)
            doc = models.FileField(upload_to="y/", blank=True, null=True)

            class Meta:
                app_label = "drf_dynamics_tests"

        class S(serializers.ModelSerializer):
            class Meta:
                model = OptModel
                fields = ["name", "logo", "doc"]

        class View(DynamicFormsMixin):
            pass

        form = View().get_dynamic_form_fields(S)
        self.assertFalse(form["name"]["required"])
        self.assertFalse(form["logo"]["required"])
        self.assertFalse(form["doc"]["required"])
        self.assertEqual(form["logo"]["html_type"], "image")
        self.assertEqual(form["logo"]["accept"], "image/*")
        self.assertEqual(form["doc"]["html_type"], "file")
        self.assertEqual(form["doc"]["accept"], "*/*")

    def test_list_of_files_is_multiple(self) -> None:
        class S(serializers.Serializer):
            attachments = serializers.ListField(child=serializers.FileField())

        class View(DynamicFormsMixin):
            pass

        form = View().get_dynamic_form_fields(S)
        self.assertTrue(form["attachments"]["accept_multiple_entries"])
        self.assertEqual(form["attachments"]["html_type"], "file")



class ChoiceEnumMultiValueTests(unittest.TestCase):
    def test_multi_value_list_representation(self) -> None:
        class OpsModel(models.Model):
            class Op(models.TextChoices):
                DEPOSIT = "DEPOSIT", "Deposit"
                PAYOUT = "PAYOUT", "Payout"

            operation_types = models.JSONField(default=list)  # stand-in for ArrayField list

            class Meta:
                app_label = "drf_dynamics_tests"

            def get_operation_types_css(self):
                return {"DEPOSIT": "success", "PAYOUT": "warning"}

        class S(serializers.ModelSerializer):
            operation_types_display = ChoiceEnumField(choice_field_name="operation_types")

            class Meta:
                model = OpsModel
                fields = ["operation_types", "operation_types_display"]

        # Manually inject choices like ArrayField.base_field would provide
        obj = OpsModel(operation_types=["DEPOSIT", "PAYOUT"])
        field = S().fields["operation_types_display"]
        field._choice_map = {"DEPOSIT": "Deposit", "PAYOUT": "Payout"}
        data = field.to_representation(obj)
        self.assertEqual(
            data,
            [
                {"value": "DEPOSIT", "title": "Deposit", "css": "success"},
                {"value": "PAYOUT", "title": "Payout", "css": "warning"},
            ],
        )

    def test_multi_value_does_not_crash_without_choice_map(self) -> None:
        class OpsModel(models.Model):
            operation_types = models.JSONField(default=list)

            class Meta:
                app_label = "drf_dynamics_tests"

        class S(serializers.ModelSerializer):
            operation_types_display = ChoiceEnumField(choice_field_name="operation_types")

            class Meta:
                model = OpsModel
                fields = ["operation_types_display"]

        obj = OpsModel(operation_types=["A", "B"])
        data = S(obj).data["operation_types_display"]
        self.assertEqual(
            data,
            [
                {"value": "A", "title": "A", "css": "default"},
                {"value": "B", "title": "B", "css": "default"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
