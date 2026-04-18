"""
Structured table-cell payloads for dynamic list UIs (versioned JSON contract).

Used with REST list serializers so a single column can carry layout metadata,
primary/secondary text, and an optional image block (logo/avatar).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

COMPOSITE_CELL_KIND: Final[str] = "dynamics.composite_cell.v1"

# Layout identifiers consumed by frontends (e.g. Angular DynamicListComponent).
COMPOSITE_LAYOUT_MEDIA_TWO_LINE: Final[str] = "media_two_line"
COMPOSITE_LAYOUT_AVATAR_NAME_EMAIL: Final[str] = "avatar_name_email"
COMPOSITE_LAYOUT_LOGO_NAME: Final[str] = "logo_name"

ALLOWED_LAYOUTS: frozenset[str] = frozenset(
    {
        COMPOSITE_LAYOUT_MEDIA_TWO_LINE,
        COMPOSITE_LAYOUT_AVATAR_NAME_EMAIL,
        COMPOSITE_LAYOUT_LOGO_NAME,
    }
)


def resolve_dotted_path(obj: Any, path: str | None) -> Any:
    """
    Walk ``obj`` using a dotted path.

    Supports model attributes and ``dict`` / ``Mapping`` keys (including nested
    JSONField data).

    Args:
        obj: Root instance (e.g. model).
        path: Dot-separated segments (e.g. ``financial_entity.name``).
            ``None`` or empty string returns ``None``.

    Returns:
        The resolved value, or ``None`` if a segment is missing.
    """
    if not path or obj is None:
        return None
    cur: Any = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate_composite_cell(data: Any) -> dict[str, Any]:
    """
    Validate and normalize a composite cell payload.

    Args:
        data: Dict from declarative :class:`CompositeCellField` or from
            ``get_<name>(obj)``.

    Returns:
        A new dict with ``kind``, ``layout``, ``primary`` (may be empty),
        optional ``secondary``, ``tertiary``, and optional ``image``.

    Raises:
        rest_framework.exceptions.ValidationError: If invalid.
    """
    if not isinstance(data, Mapping):
        raise ValidationError("Composite cell must be a JSON object.")

    kind = data.get("kind")
    if kind != COMPOSITE_CELL_KIND:
        raise ValidationError(
            f'Composite cell "kind" must be "{COMPOSITE_CELL_KIND}", '
            f"got {kind!r}."
        )

    layout = data.get("layout")
    if layout not in ALLOWED_LAYOUTS:
        allowed = sorted(ALLOWED_LAYOUTS)
        raise ValidationError(
            f"Composite cell layout must be one of {allowed}, got {layout!r}."
        )

    primary = _clean_str(data.get("primary"))
    secondary = _clean_str(data.get("secondary"))
    tertiary = _clean_str(data.get("tertiary"))

    image: dict[str, str] | None = None
    raw_image = data.get("image")
    if raw_image is not None:
        if not isinstance(raw_image, Mapping):
            raise ValidationError(
                'Composite cell "image" must be an object when present.'
            )
        url = _clean_str(raw_image.get("url"))
        alt = _clean_str(raw_image.get("alt"))
        image = {}
        if url:
            image["url"] = url
        if alt:
            image["alt"] = alt
        if not image:
            image = None

    # primary/secondary may be empty (e.g. optional FK paths); UIs should handle blanks.

    out: dict[str, Any] = {
        "kind": COMPOSITE_CELL_KIND,
        "layout": layout,
        "primary": primary,
    }
    if secondary:
        out["secondary"] = secondary
    if tertiary:
        out["tertiary"] = tertiary
    if image:
        out["image"] = image
    return out


class CompositeCellField(serializers.Field):
    """
    Read-only field that emits a **composite cell** JSON object for dynamic
    tables.

    Two modes (mutually exclusive):

    1. **Declarative** — pass ``layout`` and ``primary_path`` (dotted lookups
       from the serialized model instance, e.g. ``financial_entity.name``).
       Optional ``secondary_path``, ``tertiary_path``, ``image_url_path``,
       ``image_alt_path``. No ``get_<field_name>()`` method is required.

    2. **Serializer method** — omit ``primary_path``. Implement
       ``get_<field_name>(self, obj)`` on the parent serializer and return a
       dict that includes ``kind``, ``layout``, and the usual keys; it will be
       passed through :func:`validate_composite_cell`.

    The output is always validated with :func:`validate_composite_cell`.

    Args:
        layout: Required for declarative mode. One of: ``media_two_line``,
            ``avatar_name_email``, ``logo_name``.
        primary_path: Dotted path for the main label (declarative mode).
        secondary_path: Optional second line (e.g. entity code).
        tertiary_path: Optional third line.
        image_url_path: Optional dotted path resolving to an image URL string.
        image_alt_path: Optional dotted path for image alt text; defaults to
            primary text when the image block is present (declarative mode).

    Example (declarative):

        .. code-block:: python

            provider = CompositeCellField(
                layout="media_two_line",
                primary_path="financial_entity.name",
                secondary_path="financial_entity.code",
            )

    Example (custom method):

        .. code-block:: python

            provider = CompositeCellField()

            def get_provider(self, obj):
                return {
                    "kind": COMPOSITE_CELL_KIND,
                    "layout": "media_two_line",
                    "primary": obj.financial_entity.name,
                    "secondary": obj.financial_entity.code,
                }
    """

    def __init__(
        self,
        layout: str | None = None,
        primary_path: str | None = None,
        secondary_path: str | None = None,
        tertiary_path: str | None = None,
        image_url_path: str | None = None,
        image_alt_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("read_only", True)
        kwargs.setdefault("source", "*")
        self._declarative_layout = layout
        self.primary_path = primary_path
        self.secondary_path = secondary_path
        self.tertiary_path = tertiary_path
        self.image_url_path = image_url_path
        self.image_alt_path = image_alt_path
        super().__init__(**kwargs)

    def bind(
        self,
        field_name: str,
        parent: serializers.BaseSerializer | None,
    ) -> None:
        super().bind(field_name, parent)
        self._method_name = f"get_{field_name}"

    def to_representation(self, value: Any) -> dict[str, Any]:
        """
        Args:
            value: Model instance (``source='*'`` provides the root object).
        """
        obj = value
        if self.primary_path is not None:
            data = self._build_declarative(obj)
        else:
            if self.parent is None:
                raise ValidationError(
                    "CompositeCellField requires a bound parent serializer."
                )
            method = getattr(self.parent, self._method_name, None)
            if method is None or not callable(method):
                msg = (
                    f"CompositeCellField in method mode requires a callable "
                    f"'{self._method_name}' on the serializer, or use "
                    "declarative mode with 'primary_path'."
                )
                raise ValidationError(msg)
            data = method(obj)
        return validate_composite_cell(data)

    def _build_declarative(self, obj: Any) -> dict[str, Any]:
        if self._declarative_layout is None:
            raise ValidationError(
                "CompositeCellField: `layout` is required when "
                "`primary_path` is set."
            )
        primary = _clean_str(resolve_dotted_path(obj, self.primary_path))
        if self.secondary_path:
            sec_val = resolve_dotted_path(obj, self.secondary_path)
            secondary = _clean_str(sec_val)
        else:
            secondary = ""
        if self.tertiary_path:
            tertiary = _clean_str(resolve_dotted_path(obj, self.tertiary_path))
        else:
            tertiary = ""

        if self.image_url_path:
            url_raw = resolve_dotted_path(obj, self.image_url_path)
        else:
            url_raw = None
        if self.image_alt_path:
            alt_raw = resolve_dotted_path(obj, self.image_alt_path)
        else:
            alt_raw = None

        url = _clean_str(url_raw)
        alt = _clean_str(alt_raw)
        if not alt and primary:
            alt = primary

        image = None
        if url or alt:
            image = {}
            if url:
                image["url"] = url
            if alt:
                image["alt"] = alt

        data: dict[str, Any] = {
            "kind": COMPOSITE_CELL_KIND,
            "layout": self._declarative_layout,
            "primary": primary,
        }
        if secondary:
            data["secondary"] = secondary
        if tertiary:
            data["tertiary"] = tertiary
        if image:
            data["image"] = image
        return data
