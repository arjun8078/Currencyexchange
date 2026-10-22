from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="currency-health"),
    path("currencies/", views.currencies, name="currency-list"),
    path("convert/", views.convert, name="currency-convert"),
]
