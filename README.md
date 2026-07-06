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

---

## How to run the system (step by step)

### 1. Requirements

- **Python 3.10 or newer.** Check with:

  ```bash
  python --version
  ```

  If you don't have it, download it from <https://www.python.org/downloads/>.
  On Windows, tick **"Add Python to PATH"** during installation.

### 2. Get the code

Either clone the repository:

```bash
git clone https://github.com/patrickAdegbesan/ghot-walker-.git
cd ghot-walker-
```

…or download it as a ZIP from GitHub (**Code → Download ZIP**), extract it,
and open a terminal inside the extracted folder.

### 3. Create a virtual environment (recommended)

```bash
python -m venv venv
```

Activate it:

- **Windows:** `venv\Scripts\activate`
- **macOS / Linux:** `source venv/bin/activate`

### 4. Install the dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the application

```bash
python app.py
```

You should see Flask start up. The database (`atm_card_system.db`) and the
default administrator account are created automatically on first run.

### 6. Open the system in your browser

Go to **<http://127.0.0.1:5000>**.

### 7. Log in

| Role | Email | Password |
|---|---|---|
| Administrator (created automatically) | `admin@bank.com` | `admin123` |
| Customer | register your own at `/register` | — |

You can override the admin password by setting the `ADMIN_PASSWORD`
environment variable before the first run.

### 8. (Optional) Load demonstration data

With the server stopped, run:

```bash
flask seed
```

This creates three demo customers — `ada@example.com`, `chidi@example.com`
and `fatima@example.com` (password: `password`) — with four card requests at
different lifecycle stages. Useful for exploring the system and taking
screenshots.

### 9. Try the full workflow

1. **As a customer:** register → log in → *Request a Card* → fill the form
   (card type, scheme, delivery method, optional ID document) → submit.
   Note the tracking reference (e.g. `ATM-4F2A1B`).
2. **As the admin:** log in as `admin@bank.com` → *Requests* → open the
   request → **Approve** → *Move to "In Production"* → assign a delivery
   agent and *Move to "Dispatched"* → *Move to "Delivered"*.
3. **Track it:** the customer sees a notification at every stage, and anyone
   can check progress on the public **Track a Card** page using the
   reference code — no login needed.

### Troubleshooting

- **`pip` or `python` not found:** try `python3` / `pip3` (macOS/Linux), or
  reinstall Python with "Add to PATH" enabled (Windows).
- **Port 5000 already in use:** stop the other program, or run
  `flask run --port 5001` and open <http://127.0.0.1:5001>.
- **Start fresh:** stop the server and delete `atm_card_system.db`; it is
  recreated (with the admin account) on the next run.

---

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

## Screenshots

Screenshots of the running system are in [`docs/screenshots/`](docs/screenshots/),
and a compiled document with captioned figures is at
[`docs/System_Screenshots.docx`](docs/System_Screenshots.docx).

| # | Screen |
|---|---|
| 01 | Home page |
| 02 | Customer registration |
| 03 | Customer dashboard (my requests) |
| 04 | ATM card request form |
| 05 | Request detail with tracking timeline |
| 06 | Public tracking page |
| 07 | Customer notifications |
| 08 | Administrative dashboard |
| 09 | Admin — manage a request |
| 10 | Admin — customer records |
| 11 | Admin — activity log |
| 12 | High-contrast accessibility mode |

## Scope note

This is an academic prototype: it simulates bank-side verification, card
production and courier delivery, and does not integrate with real banking
databases, payment gateways or SMS/email gateways (notifications are stored
in-app and logged instead).
