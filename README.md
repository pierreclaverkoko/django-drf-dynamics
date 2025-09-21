# Django DRF Dynamics

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Django Version](https://img.shields.io/badge/django-4.2+-green.svg)](https://djangoproject.com)
[![DRF Version](https://img.shields.io/badge/djangorestframework-3.14+-orange.svg)](https://django-rest-framework.org)

A powerful Django third-party package that provides dynamic components for Django REST Framework, enabling rapid development of data-driven applications with dynamic filters, forms, lists, autocomplete, lookup functionality, and real-time features.

## Features

### 🔍 Dynamic Filters
- **Multiple Filter Types**: Select, autocomplete, boolean, date, datetime, range, and form value filters
- **Advanced Date Filtering**: Support for both legacy and modern date range filtering
- **Amount/Numeric Ranges**: Sophisticated filtering for monetary and numeric data
- **Metadata-Driven**: Configure filters through simple metadata definitions
- **Elasticsearch DSL Integration**: Built-in support for Elasticsearch queries

### 📝 Dynamic Forms
- **Auto-Generated Forms**: Create forms automatically from DRF serializers
- **Multiple Form Types**: Support for create, update, and detail forms
- **Nested Serializers**: Handle complex nested form structures
- **Autocomplete Fields**: Built-in autocomplete field support
- **Field Validation**: Automatic validation based on serializer constraints

### 🔍 Autocomplete & Lookup
- **Smart Object Lookup**: Efficient object lookup with multiple field support
- **Standardized Responses**: Consistent lookup response format
- **Flexible Configuration**: Customizable lookup fields and validation
- **Error Handling**: Robust error handling for lookup operations

### 📊 Dynamic Lists & Overview
- **Lightweight Lists**: Efficient list components for various data sources
- **Overview Dashboards**: Statistical overview with multiple data types
- **Multiple Data Sources**: Support for Django ORM, Elasticsearch DSL, and WebSocket
- **Pagination**: Built-in pagination support

### 🔄 Real-time Integration
- **WebSocket Support**: Real-time data updates
- **Elasticsearch DSL**: Advanced search capabilities
- **Live Filtering**: Dynamic filtering with real-time results

## Installation

```bash
pip install django-drf-dynamics
```

## Quick Setup

1. Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your apps
    'django_drf_dynamics',
]
```

2. Configure your views with dynamic mixins:

```python
from django_drf_dynamics.views import DrfDynamicsAPIViewMixin
from rest_framework import viewsets

class MyModelViewSet(DrfDynamicsAPIViewMixin, viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer
    
    # Define dynamic filters
    filterset_metadata = [
        DrfDynamicsAPIViewMixin.filter_select(
            title="Status",
            name="status",
            choices_class=MyModel.StatusChoices,
        ),
        DrfDynamicsAPIViewMixin.filter_autocomplete(
            title="Related Object",
            name="related_object",
            url="api:related-objects-autocomplete",
        ),
        DrfDynamicsAPIViewMixin.filter_date(
            title="Created Date",
            name="created_at",
        ),
    ]
```

## Core Components

### Dynamic Filters

The package provides several types of dynamic filters that can be easily configured:

#### Filter Types

- **Select Filter**: Dropdown selection from predefined choices
- **Autocomplete Filter**: Dynamic search with async loading
- **Boolean Filter**: True/False checkbox filtering
- **Date Filter**: Date range selection
- **Range Filter**: Numeric range filtering
- **Form Value Filter**: Free text input filtering

#### Usage Example

```python
from django_drf_dynamics.filters import DrfDynamicFilterBackend

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    filter_backends = [DrfDynamicFilterBackend]
    
    filterset_metadata = [
        {
            "title": "Category",
            "name": "category",
            "type": "select",
            "data": {
                "choices": [(1, "Electronics"), (2, "Books")]
            }
        },
        {
            "title": "Price Range",
            "name": "price",
            "type": "range",
            "data": {
                "min": 0,
                "max": 1000,
                "step": 10
            }
        }
    ]
```

### Dynamic Forms

Automatically generate forms from your DRF serializers:

```python
from django_drf_dynamics._utils import DynamicFormsMixin

class BookViewSet(DynamicFormsMixin, viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    create_serializer_class = BookCreateSerializer
    update_serializer_class = BookUpdateSerializer
```

#### Available Endpoints

- `GET /books/object_dynamic_form/` - Get form structure for creation
- `GET /books/object_dynamic_form/?form_name=update` - Get update form structure
- `GET /books/{id}/single_object_dynamic_form/` - Get form with object data

### Autocomplete & Lookup

```python
class AuthorViewSet(DrfDynamicsAPIViewMixin, viewsets.ModelViewSet):
    queryset = Author.objects.all()
    lookup_serializer_class = AuthorLookupSerializer
    lookup_mixin_field = ['name', 'email']
```

#### Available Endpoints

- `GET /authors/objects_autocomplete/` - Autocomplete search
- `GET /authors/object_lookup/?lookup_data=john` - Precise object lookup

### Elasticsearch DSL Integration

```python
from django_drf_dynamics.views import ElasticDslViewSet
from django_elasticsearch_dsl import Document

class ProductSearchViewSet(ElasticDslViewSet):
    document = ProductDocument
    serializer_class = ProductSerializer
    
    filter_fields = {
        'name': {
            'field': 'name.raw',
            'lookups': ['term', 'terms', 'wildcard'],
        },
        'category': {
            'field': 'category.id',
            'lookups': ['term', 'terms'],
        },
    }
```

## Advanced Features

### Multiple Serializers

Use different serializers for different actions:

```python
class ProductViewSet(DrfDynamicsAPIViewMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    list_serializer_class = ProductListSerializer
    detail_serializer_class = ProductDetailSerializer
    create_serializer_class = ProductCreateSerializer
    update_serializer_class = ProductUpdateSerializer
```

### Overview Dashboard

```python
class SalesViewSet(DrfDynamicsAPIViewMixin, viewsets.ModelViewSet):
    def get_objects_overview_data(self):
        return [
            {
                "title": "Total Sales",
                "value": "$125,430",
                "type": self.OverviewType.AMOUNT,
                "css": self.OverviewType.Data.TAG_SUCCESS,
            },
            {
                "title": "Orders Today",
                "value": 42,
                "type": self.OverviewType.NUMBER,
                "css": self.OverviewType.Data.TAG_INFO,
            }
        ]
```

### Custom Field Serializers

The package includes specialized field serializers:

```python
from django_drf_dynamics.serializers import ChoiceEnumField, JsonLoadSerializerMethodField

class ProductSerializer(serializers.ModelSerializer):
    status = ChoiceEnumField()  # Returns {"value": 1, "title": "Active", "css": "success"}
    metadata = JsonLoadSerializerMethodField()  # Auto-loads JSON fields
```

## API Endpoints

When you use the dynamic mixins, your ViewSets automatically get these additional endpoints:

### Filter & Form Endpoints
- `GET /api/model/objects_filtering_data/` - Get filtering metadata
- `GET /api/model/object_dynamic_form/` - Get form structure
- `GET /api/model/{id}/single_object_dynamic_form/` - Get form with data

### Lookup Endpoints
- `GET /api/model/objects_autocomplete/` - Autocomplete search
- `GET /api/model/object_lookup/?lookup_data=term` - Object lookup

### Overview Endpoints
- `GET /api/model/objects_overview/` - Dashboard overview data

## Frontend Integration

The package is designed to work seamlessly with frontend frameworks. All endpoints return JSON data in a consistent format that can be easily consumed by:

- React/Vue.js applications
- Django templates with AJAX
- Mobile applications
- Any HTTP client

### Example Frontend Usage

```javascript
// Get filtering options
fetch('/api/products/objects_filtering_data/')
  .then(response => response.json())
  .then(data => {
    // data.filters contains all filter definitions
    // data.ordering contains ordering options
    buildFilterForm(data.filters);
  });

// Get form structure
fetch('/api/products/object_dynamic_form/')
  .then(response => response.json())
  .then(formFields => {
    buildDynamicForm(formFields);
  });
```

## Requirements

- Python 3.10+
- Django 4.2+
- Django REST Framework 3.14+
- django-filter 25.1+

## Optional Dependencies

- `django-elasticsearch-dsl-drf` - For Elasticsearch integration
- `channels` - For WebSocket support

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Support

If you encounter any issues or have questions, please [create an issue](https://github.com/pierreclaverkoko/django-drf-dynamics/issues) on GitHub.
