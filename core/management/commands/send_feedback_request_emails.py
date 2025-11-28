from django.core.management.base import BaseCommand
from django.db.models import Count
from django_q.tasks import async_task

from core.models import Profile


class Command(BaseCommand):
    help = "Send feedback request emails to all profiles with at least 1 project"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which profiles would receive emails without actually sending them",
        )
        parser.add_argument(
            "--profile-ids",
            type=str,
            help="Comma-separated profile IDs (e.g. '1,2,3') to limit the scope",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force sending even if profile has already received a feedback request email",
        )

    def handle(self, *args, **options):
        from core.choices import EmailType
        from core.models import EmailSent

        # Get profiles with at least 1 project
        profiles = Profile.objects.annotate(project_count=Count("projects")).filter(
            project_count__gte=1
        )

        if profile_ids := options.get("profile_ids"):
            try:
                ids = [int(id.strip()) for id in profile_ids.split(",")]
                profiles = profiles.filter(id__in=ids)
            except ValueError:
                self.stdout.write(self.style.ERROR("Invalid profile IDs format"))
                return

        # Always skip profiles that have already received feedback request emails (unless --force)
        if not options.get("force"):
            sent_profile_ids = EmailSent.objects.filter(
                email_type=EmailType.FEEDBACK_REQUEST
            ).values_list("profile_id", flat=True)

            profiles = profiles.exclude(id__in=sent_profile_ids)

        if not (count := profiles.count()):
            self.stdout.write(self.style.WARNING("No profiles found"))
            return

        self.stdout.write(f"Found {count} profile(s) with at least 1 project")

        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING("\nDRY RUN - No emails will be sent\n"))
            for profile in profiles.select_related("user").iterator():
                self.stdout.write(
                    f"  - Profile {profile.id}: {profile.user.email} ({profile.projects.count()} project(s))"  # noqa: E501
                )
            return

        self.stdout.write(f"Queuing {count} feedback request email(s)...")

        sent_count = 0
        for profile in profiles.iterator():
            async_task(
                "core.tasks.send_feedback_request_email",
                profile.id,
                group="Send Feedback Request Emails",
            )
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Queued {sent_count} feedback request email(s)"))
