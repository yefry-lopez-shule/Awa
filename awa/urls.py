"""
URL configuration for awa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# No django.contrib.admin route: ADR-0005 — every screen is custom, deliberately.
from django.urls import include, path

urlpatterns = [
    # Django's set_language redirect view (#19): the language switcher POSTs
    # here, it writes the language cookie and bounces back. No account needed —
    # the choice rides in a cookie and survives every later visit.
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("studying.urls")),
    path("", include("planning.urls")),
    path("", include("reference.urls")),
    # Wired up as each app's views land (#1-#6).
]
