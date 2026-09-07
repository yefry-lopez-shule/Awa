from django.urls import path

from . import views

app_name = "studying"

urlpatterns = [
    path("onboarding/", views.onboarding, name="onboarding"),
]
