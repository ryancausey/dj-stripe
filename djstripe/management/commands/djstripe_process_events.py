from django.core.management.base import BaseCommand

from ... import models
from ... import settings as djstripe_settings
from ...mixins import VerbosityAwareOutputMixin


class Command(VerbosityAwareOutputMixin, BaseCommand):
    """Command to process all Events.

    Optional arguments are provided to limit the number of Events processed.

    Note: this is only guaranteed go back at most 30 days based on the
    current limitation of stripe's events API. See: https://stripe.com/docs/api/events
    """

    help = (
        "Process all Events. Use optional arguments to limit the Events to process. "
        "Note: this is only guaranteed go back at most 30 days based on the current "
        "limitation of stripe's events API. See:  https://stripe.com/docs/api/events"
    )

    account_ids_arg = "--account-ids"
    no_connect_arg = "--no-connect"

    def add_arguments(self, parser):
        """Add optional arugments to filter Events by."""
        # Use a mutually exclusive group to prevent multiple arguments being
        # specified together.
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--ids",
            nargs="*",
            help="An optional space separated list of specific Event IDs to sync.",
        )
        group.add_argument(
            "--failed",
            action="store_true",
            help="Syncs and processes only the events that have failed webhooks.",
        )
        group.add_argument(
            "--type",
            help=(
                "A string containing a specific event name,"
                " or group of events using * as a wildcard."
                " The list will be filtered to include only"
                " events with a matching event property."
            ),
        )
        # Add another mutually exclusive group for connect arguments.
        connect_group = parser.add_mutually_exclusive_group()
        # Allow syncing events from specific connected account IDs.
        connect_group.add_argument(
            self.account_ids_arg,
            nargs="*",
            help=(
                "An optional space separated list of specific connected Account "
                "IDs to sync events from. This would be needed if the Account "
                "wasn't synced due to a failed event and doesn't exist in the "
                "database."
            ),
        )
        connect_group.add_argument(
            self.no_connect_arg,
            action="store_true",
            help="Do not sync events from connected accounts."
        )
        # Add this so we can perform some complex validation in handle().
        self._parser = parser

    def handle(self, *args, **options):
        """Try to process Events listed from the API."""
        # Set the verbosity to determine how much we output, if at all.
        self.set_verbosity(options)

        event_ids = options["ids"]
        failed = options["failed"]
        type_filter = options["type"]
        account_ids = options["account_ids"]
        no_connect = options["no_connect"]

        # If there are no provided account IDs, then pull account IDs from the DB.
        if not account_ids and not no_connect:
            account_ids = [account.id for account in models.Account.objects.all()]

        if len(account_ids) > 1 and event_ids:
            self._parser.error(
                (
                    "Event IDs cannot be specified when multiple connected Accounts "
                    "were specified or already exist. Please sync events for one "
                    "account at a time using {account_ids}, or specify {no_connect} "
                    "to skip syncing from connected accounts."
                ).format(
                    account_ids = self.account_ids_arg,
                    no_connect = self.no_connect_arg,
                ),
            )

        # Args are mutually exclusive,
        # so output what we are doing based on that assumption.
        if failed:
            self.output("Processing all failed events")
        elif type_filter:
            self.output(
                "Processing all events that match {filter}".format(filter=type_filter)
            )
        elif event_ids:
            self.output("Processing specific events {events}".format(events=event_ids))
        else:
            self.output("Processing all available events")

        # Either use the specific event IDs to retrieve data, or use the api_list
        # if no specific event IDs are specified.
        if event_ids:
            listed_events = (
                models.Event.stripe_class.retrieve(
                    id=event_id, api_key=djstripe_settings.STRIPE_SECRET_KEY, stripe_account=account_ids[0],
                )
                for event_id in event_ids
            )
        else:
            list_kwargs = {}
            if failed:
                list_kwargs["delivery_success"] = False

            if type_filter:
                list_kwargs["type"] = type_filter

            # Use `None` for the events for our account.
            listed_events = {None: models.Event.api_list(**list_kwargs)}

            # Create a dictionary mapping a account to its events.
            if account_ids:
                listed_events = {
                    **listed_events,
                    **{
                        account_id: models.Event.api_list(stripe_account = account_id, **list_kwargs)
                        for account_id in account_ids
                    },
                }

        self.process_events(listed_events)

    def process_events(self, listed_events):
        # Process each listed event. Capture failures and continue,
        # outputting debug information as verbosity dictates.
        count = 0
        total = 0
        for account_id, event_list in listed_events.items():
            if account_id:
                self.verbose_output("  Processing events for {account}".format(account=account_id))
            else:
                self.verbose_output("  Processing events for our own account.")

            for event_data in event_list:
                try:
                    total += 1
                    event = models.Event.process(data=event_data, stripe_account=account_id)
                    count += 1
                    self.verbose_output("    Synced Event {id}".format(id=event.id))
                except Exception as exception:
                    self.verbose_output(
                        "    Failed processing Event {id}".format(id=event_data["id"])
                    )
                    self.output("  {exception}".format(exception=exception))
                    self.verbose_traceback()

        if total == 0:
            self.output("  (no results)")
        else:
            self.output(
                "  Processed {count} out of {total} Events".format(
                    count=count, total=total
                )
            )
