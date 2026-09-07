from django.urls import path

from . import views

app_name = "reference"

urlpatterns = [
    path("roadmap/", views.roadmap, name="roadmap"),
]
