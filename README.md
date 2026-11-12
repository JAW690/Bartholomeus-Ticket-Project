# Ticket Desk

A small Flask web app for submitting support tickets and tracking who is
working on them. Users can register with a one-time invite code, submit tickets,
claim open tickets, and mark claimed tickets as finished. Admins can generate
invite codes.

This project runs locally. It is not currently deployed as a public website.

## Features

- Account registration with one-time invite codes and password hashing
- Login and authenticated pages
- Ticket submission for IT, HR, Finance, and Marketing
- Claiming tickets and viewing your claimed tickets
- Finishing tickets, with an archive record
- Admin-only invite-code generation
- Dashboard counts for submitted, claimed, and open tickets

## Built with

- Python and Flask
- Flask-Login for session-based authentication
- Flask-SQLAlchemy and SQLite for data storage
- HTML, CSS, and JavaScript

## Run locally on Windows

Install Python if needed, then open PowerShell in this project folder and run:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app create-admin
```

The admin setup command prompts for your name, email, and password. It creates
the first administrator account; it will not create another if an admin already
exists.

Start the app:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:7000](http://127.0.0.1:7000) in your browser. Sign in
with the administrator account, open **Admin panel**, and generate invite
codes. Share a code with each person who should register; each code works once.

Keep the terminal running while you use the app. Press **Ctrl+C** in that
terminal to stop it. In VS Code, after creating the administrator, you can also
use **Tasks: Run Task** and choose **Run ticket app locally**.

The SQLite database is created locally under `instance`. Keep a backup if you
need to preserve your local app data.

## Run tests

With the project environment set up, run:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

## GitHub and deployment

Pushing this project to GitHub lets people view and download its source code;
GitHub does not run this Flask app or provide a live demo URL. To let someone
use it in their browser, deploy it to a hosting service and configure a
persistent database and secret key.

Before publishing, do not upload your `.venv`, local database, or secret
configuration. The included `.gitignore` excludes these local files.

## Important

This app is intended for local demos and development. Flask's built-in server
is not a production hosting solution; do not expose it directly to the
internet.
