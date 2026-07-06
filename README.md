# CardExpress — Web-Based ATM Card Request and Delivery System

A lightweight prototype of a web-based ATM card request and delivery system
for banks in Nigeria, built as a final-year Computer Science project
(Caleb University). It implements the seven modules specified in Chapter
Three of the project write-up:

| Module | Where |
|---|---|
| User registration & authentication | `/register`, `/login` |
| ATM card request (new / replacement / renewal) | `/requests/new` |
| Real-time request tracking | `/requests/<id>` and public `/track` |
| Notification management (in-app + simulated email) | `/notifications` |
| Administrative dashboard | `/admin` |
| Delivery coordination (agent assignment, dispatch) | `/admin/requests/<id>` |
| Customer profile management | `/profile` |

**Accessibility:** skip-to-content link, full keyboard navigation, semantic
HTML with ARIA live regions for status messages, screen-reader-friendly
progress tracker, and a persistent high-contrast mode toggle — supporting
the study's financial-inclusion objective.

## Technology stack

- **Frontend:** HTML, CSS, JavaScript (no frameworks — light and portable)
- **Backend:** Python 3 with Flask
- **Database:** SQLite by default (zero setup); PostgreSQL supported via the
  `DATABASE_URL` environment variable, matching the Chapter 3 methodology

## Running the system

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000>.

A default administrator account is created automatically on first run:

- **Email:** `admin@bank.com`
- **Password:** `admin123` (override with the `ADMIN_PASSWORD` environment variable)

### Optional demo data

```bash
flask seed
```

Creates three demo customers (`ada@example.com`, `chidi@example.com`,
`fatima@example.com`, password `password`) with card requests at different
lifecycle stages, useful for screenshots.

## Card request lifecycle

```
Pending → Approved → In Production → Dispatched → Delivered
        ↘ Rejected / On Hold
```

Every status change is written to the request's tracking history and
generates a customer notification (in-app, plus a simulated email logged to
the console). Dispatching requires assigning a delivery agent, which covers
the delivery-coordination requirement.

## Running the tests

```bash
python -m pytest tests/ -v
```

The test suite covers registration validation, authentication, request
submission, public tracking, the full admin approve → deliver lifecycle,
rejection handling, and access control (customers cannot reach admin pages
or other customers' requests).

## Scope note

This is an academic prototype: it simulates bank-side verification, card
production and courier delivery, and does not integrate with real banking
databases, payment gateways or SMS/email gateways (notifications are stored
in-app and logged instead).
