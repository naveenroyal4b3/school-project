"""Backup and restore.

A backup is only worth having if it restores. These tests take a real dump,
destroy the data, load it back and check the rows returned - rather than
asserting that a file was written, which is the failure mode of most backup
systems.
"""

import gzip
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.students.models import Student

from .testing import make_admin, make_organization, make_student


class BackupTests(TestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        make_admin(self.org)
        self.student = make_student(self.org, "s1", "ADM-1", "R-1")
        Attendance.objects.create(
            student=self.student, date="2026-09-01", status="PRESENT"
        )

    def test_backup_writes_a_readable_archive(self):
        with tempfile.TemporaryDirectory() as out:
            call_command("backup", output_dir=out, stdout=StringIO())

            archives = list(Path(out).glob("db-*.json.gz"))
            self.assertEqual(len(archives), 1)

            with gzip.open(archives[0], "rt", encoding="utf-8") as handle:
                records = json.load(handle)

            models = {row["model"] for row in records}
            self.assertIn("students.student", models)
            self.assertIn("attendance.attendance", models)

    def test_rebuildable_tables_are_excluded(self):
        """Content types and permissions are recreated by migrations; restoring
        stale rows collides with the ones already there."""
        with tempfile.TemporaryDirectory() as out:
            call_command("backup", output_dir=out, stdout=StringIO())
            archive = next(Path(out).glob("db-*.json.gz"))

            with gzip.open(archive, "rt", encoding="utf-8") as handle:
                models = {row["model"] for row in json.load(handle)}

        for excluded in ("contenttypes.contenttype", "auth.permission", "sessions.session"):
            self.assertNotIn(excluded, models)

    def test_keep_prunes_older_archives(self):
        with tempfile.TemporaryDirectory() as out:
            for _ in range(3):
                call_command("backup", output_dir=out, keep=2, stdout=StringIO())
            # Timestamps are per-second, so the three runs may share a name;
            # what matters is that pruning never leaves more than requested.
            self.assertLessEqual(len(list(Path(out).glob("db-*.json.gz"))), 2)


class RestoreTests(TestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.student = make_student(self.org, "s1", "ADM-RESTORE", "R-1")

    def test_a_backup_actually_restores(self):
        with tempfile.TemporaryDirectory() as out:
            call_command("backup", output_dir=out, stdout=StringIO())
            archive = next(Path(out).glob("db-*.json.gz"))

            Student.objects.all().delete()
            User.objects.all().delete()
            self.assertEqual(Student.objects.count(), 0)

            call_command("restore", str(archive), yes=True, stdout=StringIO())

        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Student.objects.get().admission_no, "ADM-RESTORE")

    def test_restore_refuses_without_confirmation(self):
        """It clears the tables it repopulates, so an accidental run would
        destroy live data."""
        with tempfile.TemporaryDirectory() as out:
            call_command("backup", output_dir=out, stdout=StringIO())
            archive = next(Path(out).glob("db-*.json.gz"))

            call_command("restore", str(archive), stdout=StringIO())   # no --yes

        # Untouched.
        self.assertEqual(Student.objects.count(), 1)

    def test_a_missing_archive_is_reported_not_ignored(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("restore", "nowhere/missing.json.gz", yes=True, stdout=StringIO())
