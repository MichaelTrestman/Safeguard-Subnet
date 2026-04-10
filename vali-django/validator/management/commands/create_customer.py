"""
Create a customer user + CustomerProfile and associate with target(s).

Usage:
    python manage.py create_customer customer1 customerpassword1 --target-hotkey 5F...
    python manage.py create_customer customer1 customerpassword1 --target-name demo-client
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from validator.models import CustomerProfile, RegisteredTarget


class Command(BaseCommand):
    help = "Create a customer user with a CustomerProfile linked to target(s)"

    def add_arguments(self, parser):
        parser.add_argument("username", help="Login username for the customer")
        parser.add_argument("password", help="Login password")
        parser.add_argument(
            "--target-hotkey",
            nargs="+",
            default=[],
            help="Client hotkey(s) of RegisteredTarget(s) to associate",
        )
        parser.add_argument(
            "--target-name",
            nargs="+",
            default=[],
            help="Name(s) of RegisteredTarget(s) to associate",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        # Resolve targets
        targets = []
        for hotkey in options["target_hotkey"]:
            try:
                t = RegisteredTarget.objects.get(client_hotkey=hotkey)
            except RegisteredTarget.DoesNotExist:
                raise CommandError(f"No RegisteredTarget with hotkey {hotkey}")
            targets.append(t)
        for name in options["target_name"]:
            try:
                t = RegisteredTarget.objects.get(name=name)
            except RegisteredTarget.DoesNotExist:
                raise CommandError(f"No RegisteredTarget with name '{name}'")
            targets.append(t)

        # Create or update user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_staff": False},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"Created user '{username}'")
        else:
            self.stdout.write(f"User '{username}' already exists")

        # Create or get profile
        profile, _ = CustomerProfile.objects.get_or_create(user=user)

        # Associate targets
        for t in targets:
            profile.targets.add(t)
            self.stdout.write(f"  Linked target: {t.name} ({t.client_hotkey[:16]}...)")

        if not targets:
            self.stdout.write(
                "  No targets specified. Use --target-hotkey or --target-name "
                "to associate targets later."
            )

        self.stdout.write(self.style.SUCCESS(
            f"Customer '{username}' ready — "
            f"{profile.targets.count()} target(s) linked"
        ))
