"""
dj-stripe - Views related to the djstripe app.
"""
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from .models import WebhookEventTrigger
from .models.webhooks import EndpointType

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name="dispatch")
class ProcessWebhookView(View):
    """
    A Stripe Webhook handler view.

    This will create a WebhookEventTrigger instance, verify it,
    then attempt to process it.

    If the webhook cannot be verified, returns HTTP 400.

    If an exception happens during processing, returns HTTP 500.
    """
    endpoint_type = EndpointType.ACCOUNT

    def post(self, request):
        if "HTTP_STRIPE_SIGNATURE" not in request.META:
            # Do not even attempt to process/store the event if there is
            # no signature in the headers so we avoid overfilling the db.
            return HttpResponseBadRequest()

        trigger = WebhookEventTrigger.from_request(request, endpoint_type=self.endpoint_type)

        if trigger.is_test_event:
            # Since we don't do signature verification, we have to skip trigger.valid
            return HttpResponse("Test webhook successfully received!")

        if not trigger.valid:
            # Webhook Event did not validate, return 400
            return HttpResponseBadRequest()

        return HttpResponse(str(trigger.id))
