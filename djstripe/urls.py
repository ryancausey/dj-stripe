"""
Urls related to the djstripe app.

Wire this into the root URLConf this way::

    re_path(r"^stripe/", include("djstripe.urls", namespace="djstripe")),
    # url can be changed
    # Call to 'djstripe.urls' and 'namespace' must stay as is

Call it from reverse()::

    reverse("djstripe:subscribe")

Call from url tag::

    {% url "djstripe:subscribe" %}
"""
from django.urls import re_path

from . import settings as app_settings
from . import views
from .models.webhooks import EndpointType

app_name = "djstripe"

urlpatterns = [
    # Webhook
    re_path(
        app_settings.DJSTRIPE_WEBHOOK_URL,
        views.ProcessWebhookView.as_view(endpoint_type=EndpointType.ACCOUNT),
        name="webhook",
    ),
    re_path(
        app_settings.DJSTRIPE_CONNECT_WEBHOOK_URL,
        views.ProcessWebhookView.as_view(endpoint_type=EndpointType.CONNECT),
        name="connect_webhook",
    ),
]
