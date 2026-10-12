from django.urls import path

from .views import CorridorForecastView

urlpatterns = [
    path("forecast/corridor/", CorridorForecastView.as_view(), name="corridor-forecast")
]
