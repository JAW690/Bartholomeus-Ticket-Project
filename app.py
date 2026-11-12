import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import click
from flask import Flask, render_template, redirect, request, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import DateTime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///base.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    submitted_tickets_count = db.Column(db.Integer, default=0, nullable=False)
    claimed_tickets_count = db.Column(db.Integer, default=0, nullable=False)
    registered_at = db.Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    # Relationship to Invites
    invites = db.relationship('Invite', backref='activated_by_user', lazy=True)


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invite_code = db.Column(db.String(100), unique=True, nullable=False)
    activated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class Tickets(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # New fields
    claimed = db.Column(db.Boolean, default=False, nullable=False)
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    claimed_date = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.String(1000), nullable=True)

    # Relationships (adjust according to your existing relationships)
    submitted_by = db.relationship('User', foreign_keys=[user_id], backref='submitted_tickets', lazy=True)
    claimer = db.relationship('User', foreign_keys=[claimed_by], backref='claimed_tickets', lazy=True)


class DeletedTickets(db.Model):
    __tablename__ = 'deleted_tickets'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # New fields
    claimed = db.Column(db.Boolean, default=False, nullable=False)
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    claimed_date = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationships (adjust according to your existing relationships)
    submitted_by = db.relationship('User', foreign_keys=[user_id], backref='submitted_deleted_tickets', lazy=True)
    claimer = db.relationship('User', foreign_keys=[claimed_by], backref='claimed_deleted_tickets', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.cli.command("create-admin")
def create_admin():
    """Create the first administrator account from an interactive prompt."""
    db.create_all()
    if User.query.filter_by(is_admin=True).first():
        raise click.ClickException("An administrator already exists.")

    name = click.prompt("First name").strip()
    surname = click.prompt("Last name").strip()
    email = click.prompt("Email").strip().lower()
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    if (
        not name
        or not surname
        or len(name) > 100
        or len(surname) > 100
        or len(email) > 120
        or "@" not in email
        or len(password) < 8
    ):
        raise click.ClickException(
            "Enter a name, valid email address, and password of at least 8 characters."
        )
    if User.query.filter_by(email=email).first():
        raise click.ClickException("That email address is already registered.")

    admin_user = User(
        name=name,
        surname=surname,
        email=email,
        password=generate_password_hash(password),
        is_admin=True,
    )
    db.session.add(admin_user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise click.ClickException("Could not create administrator: email already exists.") from error
    click.echo(f"Administrator account created for {email}.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Redirect already authenticated users to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get("name", "").strip()
        surname = request.form.get("surname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        invite_code = request.form.get("invite_code", "").strip()

        if not all([name, surname, email, password, invite_code]):
            flash("All fields, including an invite code, are required.", "warning")
            return redirect(url_for("register"))
        if (
            len(name) > 100
            or len(surname) > 100
            or len(email) > 120
            or "@" not in email
        ):
            flash(
                "Enter a valid email address and keep names within 100 characters.",
                "warning",
            )
            return redirect(url_for("register"))
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'warning')
            return redirect(url_for('register'))

        invite = Invite.query.filter_by(invite_code=invite_code).first()
        if not invite or invite.activated_by is not None:
            flash("That invite code is invalid or has already been used.", "danger")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists.', 'warning')
            return redirect(url_for('register'))

        new_user = User(
            name=name,
            surname=surname,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(new_user)
        invite.activated_by_user = new_user
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Could not complete registration. Check your email and invite code.", "danger")
            return redirect(url_for("register"))

        login_user(new_user)
        flash('Registration successful! You are now logged in.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect already authenticated users to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                target = urlsplit(urljoin(request.host_url, next_page))
                if target.scheme in ("http", "https") and target.netloc == request.host:
                    return redirect(target.geturl())
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You must be an administrator to access this page.', 'danger')
        return redirect(url_for('dashboard'))
    # Admin-only content goes here
    return render_template('admin.html')

@app.route('/generate_invites', methods=['POST'])
@login_required
def generate_invites():
    if not current_user.is_admin:
        flash('You must be an administrator to access this feature.', 'danger')
        return redirect(url_for('index'))

    try:
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        flash("Enter a number of invite codes between 1 and 100.", "danger")
        return redirect(url_for("admin"))
    if not 1 <= quantity <= 100:
        flash("Generate between 1 and 100 invite codes at a time.", "danger")
        return redirect(url_for("admin"))

    generated_codes = []

    for _ in range(quantity):
        invite_code = secrets.token_urlsafe(20)
        new_invite = Invite(invite_code=invite_code, activated_by=None)
        db.session.add(new_invite)
        generated_codes.append(invite_code)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Could not generate invite codes. Please try again.", "danger")
        return redirect(url_for("admin"))

    session['generated_codes'] = generated_codes

    flash(f'Successfully generated {quantity} invite codes.', 'success')
    return redirect(url_for('admin'))

@app.route('/dashboard')
@login_required
def dashboard():
    tickets = Tickets.query.filter_by(claimed=False).order_by(Tickets.created_at.desc()).all()
    total_tickets_count = Tickets.query.count()
    user_tickets_count = Tickets.query.filter_by(user_id=current_user.id).count()
    total_claimed_tickets = Tickets.query.filter_by(claimed=True).count()
    user_claimed_tickets_count = Tickets.query.filter_by(claimed_by=current_user.id).count()
    total_unclaimed_tickets = total_tickets_count - total_claimed_tickets
    user_unclaimed_tickets = user_tickets_count - Tickets.query.filter_by(
        user_id=current_user.id, claimed=True
    ).count()
    return render_template('dashboard.html',
                           tickets=tickets,
                           total_tickets_count=total_tickets_count,
                           total_claimed_tickets=total_claimed_tickets,
                           user_tickets_count=user_tickets_count,
                           user_claimed_tickets_count=user_claimed_tickets_count,
                           total_unclaimed_tickets=total_unclaimed_tickets,
                           user_unclaimed_tickets=user_unclaimed_tickets)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/ticket', methods=['GET', 'POST'])
@login_required
def ticket():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        department = request.form.get('department', '').strip()
        description = request.form.get('description', '').strip()
        if not all([title, department, description]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('ticket'))
        if len(title) > 100 or len(description) > 1000:
            flash("Title must be at most 100 characters and description at most 1000.", "danger")
            return redirect(url_for("ticket"))
        if department not in {"IT", "HR", "Finance", "Marketing"}:
            flash("Choose a valid department.", "danger")
            return redirect(url_for("ticket"))

        new_ticket = Tickets(
            title=title,
            department=department,
            description=description,
            user_id=current_user.id,
        )
        db.session.add(new_ticket)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Could not save submitted ticket")
            flash('There was an error submitting your ticket.', 'danger')
            return redirect(url_for("ticket"))

        flash('Your ticket has been submitted successfully.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('ticket.html')


@app.route('/claim_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def claim_ticket(ticket_id):
    ticket = Tickets.query.filter_by(id=ticket_id, claimed=False).first()
    if ticket is None:
        return jsonify({'message': 'Ticket is already claimed or does not exist.'}), 404

    ticket.claimed = True
    ticket.claimed_by = current_user.id
    ticket.claimed_date = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not claim ticket %s", ticket_id)
        return jsonify({'message': 'The ticket could not be claimed. Please try again.'}), 500
    return jsonify({'message': 'Ticket claimed successfully.'}), 200


@app.route('/my_tickets')
@login_required
def my_tickets():
    tickets = Tickets.query.filter(Tickets.claimed_by == current_user.id).all()
    return render_template('my_tickets.html', tickets=tickets)


@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    ticket = Tickets.query.filter_by(id=ticket_id).first()

    if ticket is None:
        return jsonify({'message': 'Ticket not found.'}), 404
    if ticket.claimed_by != current_user.id and not current_user.is_admin:
        return jsonify({'message': 'Only the claimant or an administrator can finish this ticket.'}), 403

    deleted_ticket = DeletedTickets(
        id=ticket.id,
        title=ticket.title,
        department=ticket.department,
        description=ticket.description,
        created_at=ticket.created_at,
        user_id=ticket.user_id,
        claimed=ticket.claimed,
        claimed_by=ticket.claimed_by,
        claimed_date=ticket.claimed_date,
        deleted_by=current_user.id,
        deleted_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )

    db.session.add(deleted_ticket)
    db.session.delete(ticket)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not finish ticket %s", ticket_id)
        return jsonify({'message': 'The ticket could not be finished. Please try again.'}), 500

    return jsonify({'message': 'Ticket marked as finished.'}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host="127.0.0.1", port=7000)
