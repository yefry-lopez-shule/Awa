from django.urls import path

from . import views

app_name = "studying"

urlpatterns = [
    path("onboarding/", views.onboarding, name="onboarding"),
    path("degree-map/", views.degree_map, name="degree_map"),
    path("course/<int:course_id>/", views.course_detail, name="course_detail"),
]
