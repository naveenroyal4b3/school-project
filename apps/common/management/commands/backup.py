"""Database and media backup.

The project document's System Administration module asks for backup and
restore. This wraps ``dumpdata`` rather than a database-specific tool so the
same command works whether the deployment is on SQLite or MySQL.

Content types and permissions are excluded: they are rebuilt from the code by
migrations, and restoring stale rows collides with the ones already there.
"""

import datetime
import gzip
import shutil
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

EXCLUDED = [
    "contenttypes",
    "auth.permission",
    "sessions",
    "admin.logentry",
    # Blacklisted tokens are worthless after a restore and can be large.
    "token_blacklist",
]


class Command(BaseCommand):
    help = "Write a compressed backup of the database, and optionally media files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir", default="backups",
            help="Where to write the archive (default: ./backups).",
        )
        parser.add_argument(
            "--with-media", action="store_true",
            help="Also archive MEDIA_ROOT (profile photos, logos).",
        )
        parser.add_argument(
            "--keep", type=int, default=0,
            help="Delete all but the newest N database backups. 0 keeps everything.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        out_dir = Path(options["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        target = out_dir / f"db-{stamp}.json.gz"
        plain = out_dir / f"db-{stamp}.json"

        self.stdout.write("Dumping database...")
        try:
            with plain.open("w", encoding="utf-8") as handle:
                call_command(
                    "dumpdata",
                    *[f"--exclude={label}" for label in EXCLUDED],
                    natural_foreign=True,
                    natural_primary=True,
                    indent=2,
                    stdout=handle,
                )

            # Compressed after the fact rather than streamed, so a failure
            # mid-dump leaves a readable partial file instead of a corrupt
            # archive that looks valid until it is needed.
            with plain.open("rb") as src, gzip.open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        finally:
            plain.unlink(missing_ok=True)

        size_mb = target.stat().st_size / 1_048_576
        self.stdout.write(self.style.SUCCESS(f"  {target}  ({size_mb:.2f} MB)"))

        if options["with_media"]:
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists() and any(media_root.iterdir()):
                archive = shutil.make_archive(
                    str(out_dir / f"media-{stamp}"), "zip", root_dir=media_root
                )
                self.stdout.write(self.style.SUCCESS(f"  {archive}"))
            else:
                self.stdout.write("  No media files to archive.")

        keep = options["keep"]
        if keep > 0:
            backups = sorted(out_dir.glob("db-*.json.gz"), reverse=True)
            for stale in backups[keep:]:
                stale.unlink()
                self.stdout.write(f"  removed {stale.name}")

        if not target.exists() or target.stat().st_size == 0:
            raise CommandError("Backup produced no output.")
