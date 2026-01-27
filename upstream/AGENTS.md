# Upstream Healthcare Platform - Agent Memory

This file captures codebase patterns, conventions, and gotchas discovered during development.

## Django REST Framework Patterns

### API Endpoint Structure

Standard pattern for creating REST endpoints:

1. **Model** (`models.py`) - Define data structure
2. **Serializer** (`serializers.py`) - Handle JSON <-> Model conversion
3. **ViewSet** (`views.py`) - Implement business logic
4. **Router** (`urls.py`) - Register endpoint

### Test Organization

Tests are organized by feature in separate files:
- `tests_api.py` - API endpoint tests
- `tests_<feature>.py` - Feature-specific tests
- Use fixtures from `test_fixtures.py`

### Quality Gates

Before committing, ensure these pass:
```bash
pytest                                    # Tests with 25% coverage minimum
python manage.py check                    # Django system check
python manage.py makemigrations --check   # No missing migrations
```

## Filtering and Pagination

This project uses:
- `django_filters.FilterSet` for complex filtering
- `rest_framework.filters.SearchFilter` for search
- Standard DRF pagination (PageNumberPagination)

Example:
```python
from django_filters import rest_framework as filters

class MyModelFilter(filters.FilterSet):
    class Meta:
        model = MyModel
        fields = ['field1', 'field2']

class MyViewSet(viewsets.ModelViewSet):
    filterset_class = MyModelFilter
    search_fields = ['name', 'description']
```

## Authentication & Permissions

- JWT authentication via `rest_framework_simplejwt`
- Always set permission classes on viewsets
- Default to `IsAuthenticated` for protected endpoints
- Use `AllowAny` only for public endpoints

## Migrations

- Always generate migrations: `python manage.py makemigrations`
- Review generated migrations before committing
- Migrations run sequentially - never skip or reorder
- Test migrations in isolation before committing

## Testing Best Practices

1. Use `APITestCase` for API endpoint tests
2. Leverage existing fixtures from `test_fixtures.py`
3. Test both success and error cases
4. Use `APIClient` for API requests
5. Assert status codes and response data structure

## Settings Organization

Multiple settings files:
- `settings/base.py` - Shared settings
- `settings/development.py` - Development overrides
- `settings/test.py` - Test environment settings

Never modify test settings unless explicitly required by the story.

## Discovered Patterns

(Ralph will append new patterns discovered during autonomous iterations)

## OpenAPI/DRF Spectacular Documentation Patterns

### @extend_schema Examples

DRF Spectacular supports rich API examples via OpenApiExample:

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    examples=[
        OpenApiExample(
            "Example Name",
            value={"key": "value"},
            response_only=True,  # or request_only=True
        ),
    ],
)
```

### Pagination Documentation

Standard pattern for documenting paginated endpoints:

```python
parameters=[
    OpenApiParameter(
        name="page",
        type=int,
        description="Page number for pagination (default: 1)",
        required=False,
    ),
    OpenApiParameter(
        name="page_size",
        type=int,
        description="Number of results per page (default: 100)",
        required=False,
    ),
],
examples=[
    OpenApiExample(
        "Paginated Response",
        value={
            "count": 150,
            "next": "https://api.example.com/api/resource/?page=2",
            "previous": None,
            "results": [...]
        },
        response_only=True,
    ),
],
```

### Line Length for Examples

When example URLs exceed 88 characters (flake8 E501), split with parentheses:

```python
"next": (
    "https://api.example.com/api/resource/"
    "?param1=value1&param2=value2"
),
```

### OpenAPI Schema Validation

Always validate schema after adding documentation:

```bash
python manage.py spectacular --validate
```

This catches schema errors and ensures examples are valid.
