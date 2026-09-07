from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("availability/", views.availability_template, name="availability_template"),
]
