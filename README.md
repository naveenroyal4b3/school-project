# Smart-Student Management System

A Django + Django REST Framework system for school and college administration:
students, faculty, academics, attendance (including QR bus IN/OUT), transport
with live bus tracking, fees, examinations, notifications, and reporting.

Built against `Smart_SMS-ProjectDocument.pdf`.

---

## Quick start (local, no database server)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt

copy .env.example .env          # cp on Linux/macOS - then set SECRET_KEY
python manage.py migrate
python manage.py seed_demo      # optional: demo college with 12 students
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. After `seed_demo`, sign in as `admin` /
`Demo!Pass2026` (also `teacher1`, `student1`, `driver1`, `parent1`).

Generate a `SECRET_KEY` with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Running with Docker and MySQL

Requires Docker Desktop. Brings up MySQL 8, Gunicorn and Nginx together:

```bash
docker compose up --build
```

Then <http://localhost/>. Migrations and `collectstatic` run automatically from
`entrypoint.sh`, which waits for MySQL to accept connections first. MySQL is
published on host port **3307** so it will not clash with a locally installed
MySQL.

Set `SECRET_KEY` in `.env` before starting - Compose refuses to boot without it.

---

## Architecture

```
Browser (Bootstrap 5 templates, fetch + JWT)
    |
    v
Django REST Framework API  ──  JWT auth (SimpleJWT), role-based permissions
    |
    v
MySQL (Docker) or SQLite (local dev)
```

Templates are thin: each page loads and then calls the REST API with the token
it holds in `localStorage`. All access control lives in the API, so there is no
second copy of the rules in template logic to drift out of sync.

### Apps

| App | Responsibility |
| --- | --- |
| `accounts` | Custom `User` with six roles, registration, JWT login |
| `organizations` | Tenants - one row per college |
| `academics` | Departments, courses, academic years, classes, sections, subjects |
| `students` | Student records |
| `parents` | Guardians; one parent to many students |
| `teachers` | Faculty records |
| `transport` | Drivers, routes, stops, buses, trips, GPS pings |
| `attendance` | Academic attendance, student QR cards, bus IN/OUT scans |
| `fees` | Fee structures, payments, receipts |
| `examinations` | Exams, schedules, results, grade calculation |
| `notifications` | Stored alerts with pluggable SMS/email delivery |
| `dashboard` | Aggregate statistics and reports |
| `common` | Shared permissions, scoping mixin, test factories, seeder |
| `web` | Server-rendered page shells |

---

## Security model

Two rules hold the system together. Both are covered by tests.

**Everything is closed by default.** `DEFAULT_PERMISSION_CLASSES` is
`IsAuthenticated`, so a new view is private unless it opts out. Only
registration and login declare `AllowAny`.

**Every query is scoped to one organization.** `OrganizationScopedMixin` filters
each view to the caller's college. A user with no organization sees nothing
rather than everything, so a misconfigured account fails closed.

Roles map to the document's five actors:

| Document actor | `User.Role` | Can write |
| --- | --- | --- |
| Admin | `SUPER_ADMIN`, `ORGANIZATION_ADMIN` | Everything in their college |
| Faculty | `TEACHER` | Academic records, attendance, results |
| Student | `STUDENT` | Nothing; reads own college's published data |
| Parent | `PARENT` | Nothing; reads and receives alerts |
| Driver | `DRIVER` | Trips, GPS pings, bus scans |

Other deliberate choices:

- Public registration cannot set `role` - self-registered users are always
  `STUDENT`, and an admin promotes them. Accepting a role on an `AllowAny`
  endpoint would let anyone register as `SUPER_ADMIN`.
- QR codes are random UUIDs, not admission numbers. A guessable code would let
  anyone forge a bus scan for a student who was never aboard.
- Exam results stay hidden until an admin publishes the exam.
- `marked_by` on attendance is taken from the session, never the payload.
- Grades are computed on save; a client-supplied grade is ignored.

---

## API

All endpoints are under `/api/` and need `Authorization: Bearer <token>` except
registration and login.

### Auth
| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/accounts/register/` | Self-registration (always `STUDENT`) |
| POST | `/api/accounts/login/` | Returns access + refresh tokens |
| POST | `/api/token/refresh/` | Exchange a refresh token |

### Core records
| Method | Endpoint |
| --- | --- |
| GET, POST | `/api/students/`, `/api/teachers/`, `/api/parents/` |
| GET, PUT, DELETE | `/api/students/<id>/` (and the same for the others) |
| GET, POST | `/api/organizations/` |
| GET, POST | `/api/academics/departments/`, `courses/`, `academic-years/`, `classrooms/`, `sections/`, `subjects/` |

### Attendance
| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET, POST | `/api/attendance/` | Records; filter by `?student=`, `?from=`, `?to=` |
| POST | `/api/attendance/bulk/` | Mark a whole class in one transaction |
| POST | `/api/attendance/scan/` | ID-card scan -> bus IN/OUT + guardian alert |
| GET, POST | `/api/attendance/qr-codes/` | Issue student ID cards |
| GET | `/api/attendance/bus/` | Raw scan log |

### Transport
| Method | Endpoint |
| --- | --- |
| GET, POST | `/api/transport/drivers/`, `routes/`, `stops/`, `buses/`, `assignments/`, `trips/`, `locations/` |
| POST | `/api/transport/trips/<id>/start/`, `/end/` |
| GET | `/api/transport/tracking/` - newest position per bus |

### Fees, exams, notifications
| Method | Endpoint |
| --- | --- |
| GET, POST | `/api/fees/`, `/api/fees/payments/` |
| GET | `/api/fees/payments/<id>/receipt/` |
| GET | `/api/fees/students/<id>/summary/` |
| GET, POST | `/api/examinations/`, `schedules/`, `results/` |
| POST | `/api/examinations/<id>/publish/` |
| GET | `/api/examinations/performance/<student_id>/` |
| GET | `/api/notifications/` (own inbox) |
| POST | `/api/notifications/sms/` (admin send) |

### Dashboard and reports
`/api/dashboard/`, `/api/reports/daily/?date=`, `/api/reports/monthly/?year=&month=`,
`/api/reports/fees/`, `/api/reports/exams/`

---

## Pages

`/login/`, `/` (dashboard), `/students/`, `/attendance/`, `/fees/`,
`/tracking/` (live map), `/admin/` (Django admin).

Bus tracking uses OpenStreetMap via Leaflet - the free option in the document's
technology stack, with no API key to manage.

---

## Notifications

Alerts are stored first and delivered second, so a failing gateway loses the
delivery attempt but never the record that an alert was owed. Delivery failures
are recorded on the row and never raised at the caller, because the callers are
things like a bus scan or a fee payment which must not fail if an SMS provider
is down.

The default SMS backend logs instead of sending, so development and tests make
no network calls and incur no charges. To go live, implement a class with a
`send(phone_number, message)` method and point `SMS_BACKEND` at it.

---

## Tests

```bash
python manage.py test
```

55 tests covering access control, multi-tenant isolation, the QR scan flow,
bulk attendance atomicity, receipt numbering, grade calculation, result
visibility, trip lifecycle, live tracking and report arithmetic.

---

## Configuration

Everything is read from `.env` (see `.env.example`). Nothing sensitive is
committed - `.env` is gitignored and has never been in the history.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Required. Django signing key |
| `DEBUG` | `True` locally, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Database; defaults to SQLite |
| `SMS_BACKEND` | Dotted path to an SMS backend; empty logs instead |
| `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` | Email delivery |

`gunicorn` is installed in the Docker image rather than listed in
`requirements.txt`, since it does not install on Windows.
