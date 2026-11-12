import unittest

from app import DeletedTickets, Invite, Tickets, User, app, db
from werkzeug.security import check_password_hash, generate_password_hash


class TicketAppTests(unittest.TestCase):
    def setUp(self):
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SECRET_KEY="test-secret",
        )
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def create_user(self, email, is_admin=False):
        user = User(
            name="Test",
            surname="User",
            email=email,
            password=generate_password_hash("password123"),
            is_admin=is_admin,
        )
        db.session.add(user)
        db.session.commit()
        return user

    def login(self, email):
        return self.client.post(
            "/login",
            data={"email": email, "password": "password123"},
            follow_redirects=True,
        )

    def test_registration_requires_and_consumes_an_invite(self):
        invite = Invite(invite_code="one-use-code")
        db.session.add(invite)
        db.session.commit()

        rejected = self.client.post(
            "/register",
            data={
                "name": "New",
                "surname": "User",
                "email": "new@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(rejected.status_code, 302)
        self.assertEqual(User.query.count(), 0)

        response = self.client.post(
            "/register",
            data={
                "name": "New",
                "surname": "User",
                "email": "new@example.com",
                "password": "password123",
                "invite_code": "one-use-code",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(email="new@example.com").one()
        self.assertTrue(check_password_hash(user.password, "password123"))
        self.assertEqual(invite.activated_by, user.id)

        with app.test_client() as second_client:
            replay = second_client.post(
                "/register",
                data={
                    "name": "Other",
                    "surname": "User",
                    "email": "other@example.com",
                    "password": "password123",
                    "invite_code": "one-use-code",
                },
            )
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(User.query.count(), 1)

    def test_create_admin_cli_bootstraps_first_admin(self):
        result = app.test_cli_runner().invoke(
            args=["create-admin"],
            input=(
                "First\n"
                "Admin\n"
                "admin@example.com\n"
                "password123\n"
                "password123\n"
            ),
        )
        self.assertEqual(result.exit_code, 0, result.output)
        admin = User.query.filter_by(email="admin@example.com").one()
        self.assertTrue(admin.is_admin)
        self.assertTrue(check_password_hash(admin.password, "password123"))

    def test_login_rejects_bad_password_and_accepts_good_password(self):
        user = User(
            name="Test",
            surname="User",
            email="test@example.com",
            password=generate_password_hash("password123"),
        )
        db.session.add(user)
        db.session.commit()

        denied = self.client.post(
            "/login",
            data={"email": user.email, "password": "wrong-password"},
        )
        self.assertEqual(denied.status_code, 200)
        accepted = self.client.post(
            "/login",
            data={"email": user.email, "password": "password123"},
            follow_redirects=True,
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertIn(b"Tickets", accepted.data)

    def test_ticket_workflow_updates_dashboard_and_archive(self):
        user = self.create_user("worker@example.com")
        self.login(user.email)

        created = self.client.post(
            "/ticket",
            data={
                "title": "Laptop issue",
                "department": "IT",
                "description": "It will not start.",
            },
            follow_redirects=True,
        )
        self.assertEqual(created.status_code, 200)
        ticket = Tickets.query.one()

        dashboard = self.client.get("/dashboard")
        self.assertIn(b'id="total_unclaimed_tickets">1</span>', dashboard.data)
        claimed = self.client.post(f"/claim_ticket/{ticket.id}")
        self.assertEqual(claimed.status_code, 200)
        self.assertTrue(Tickets.query.one().claimed)
        self.assertEqual(Tickets.query.one().claimed_by, user.id)

        my_tickets = self.client.get("/my_tickets")
        self.assertIn(b"Laptop issue", my_tickets.data)
        finished = self.client.post(f"/delete_ticket/{ticket.id}")
        self.assertEqual(finished.status_code, 200)
        self.assertEqual(Tickets.query.count(), 0)
        self.assertEqual(DeletedTickets.query.count(), 1)

    def test_only_claimant_or_admin_can_finish_ticket(self):
        owner = self.create_user("owner@example.com")
        other = self.create_user("other@example.com")
        ticket = Tickets(
            title="Owned ticket",
            department="IT",
            description="Details",
            user_id=owner.id,
            claimed=True,
            claimed_by=owner.id,
        )
        db.session.add(ticket)
        db.session.commit()
        self.login(other.email)

        response = self.client.post(f"/delete_ticket/{ticket.id}")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Tickets.query.count(), 1)

    def test_admin_can_generate_bounded_invites(self):
        admin = self.create_user("admin@example.com", is_admin=True)
        self.login(admin.email)

        response = self.client.post("/generate_invites", data={"quantity": "2"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invite.query.count(), 2)

        invalid = self.client.post("/generate_invites", data={"quantity": "101"})
        self.assertEqual(invalid.status_code, 302)
        self.assertEqual(Invite.query.count(), 2)

    def test_non_admin_cannot_generate_invites(self):
        user = self.create_user("user@example.com")
        self.login(user.email)

        response = self.client.post("/generate_invites", data={"quantity": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invite.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
