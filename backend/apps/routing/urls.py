from django.urls import path

from .views import AutocompleteView

urlpatterns = [
    path(
        "geocode/autocomplete/", AutocompleteView.as_view(), name="geocode-autocomplete"
    ),
]
