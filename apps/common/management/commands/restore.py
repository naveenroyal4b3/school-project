"""Restore a backup written by the ``backup`` command.

Destructive by nature: loading a dump on top of live data would collide on
every unique key, so the restore clears the tables it is about to repopulate.
That makes confirmation mandatory rather than a nicety.
"""

import gzip
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Restore the database from a backup archive. This replaces existing data."

    def add_arguments(self, parser):
        parser.add_argument("archive", help="Path to a db-*.json.gz backup.")
        parser.add_argument(
            "--yes", action="store_true",
            help="Skip the confirmation prompt. Required for unattended runs.",
        )

    def handle(self, *args, **options):
        archive = Path(options["archive"])
        if not archive.exists():
            raise CommandError(f"No such backup: {archive}")

        if not options["yes"]:
            # stdin is unavailable in most automated contexts, so refuse rather
            # than hang or, worse, proceed unconfirmed.
            self.stdout.write(self.style.WARNING(
                "This replaces the current database contents.\n"
                "Re-run with --yes to confirm."
            ))
            return

        with tempfile.TemporaryDirectory() as workdir:
            plain = Path(workdir) / "restore.json"

            self.stdout.write(f"Reading {archive.name}...")
            with gzip.open(archive, "rb") as src, plain.open("wb") as dst:
                shutil.copyfileobj(src, dst)

            self.stdout.write("Clearing existing data...")
            # flush drops rows but keeps the schema, so migrations do not have
            # to be re-run and the loaded dump lines up with the current models.
            call_command("flush", "--no-input")

            self.stdout.write("Loading...")
            # One transaction: a dump that fails halfway would otherwise leave
            # the database holding part of one backup and part of nothing.
            with transaction.atomic():
                call_command("loaddata", str(plain))

        self.stdout.write(self.style.SUCCESS(
            "Restore complete. Superuser accounts came from the backup, so sign "
            "in with the credentials that were valid when it was taken."
        ))
