from django.contrib.auth.models import User
from django.test import Client, TestCase

from .social import SSO_MESSAGE


class AccountFlows(TestCase):
    def setUp(self):
        self.web = Client()
        self.native = Client(HTTP_ACCEPT="application/json")
        self.password = "learn-together-783!"
        self.web.post("/signup/", {"username": "Sari@example.com", "first_name": "Sari",
                                  "password1": self.password, "password2": self.password})
        response = self.native.post("/api/account/signup/", {"username": "adi@example.com", "first_name": "Adi",
                                    "password1": self.password, "password2": self.password})
        self.assertEqual(response.status_code, 200)

    def test_email_profile_and_verification(self):
        self.web.post("/logout/")
        self.assertEqual(self.web.get("/profile/").status_code, 302)
        self.web.post("/login/", {"username": "SARI@example.com", "password": self.password})
        self.assertContains(self.web.get("/profile/"), "Belum terverifikasi")
        self.web.post("/profile/", {"first_name": "Sari UI", "verified": "true"})
        self.assertContains(self.web.post("/profile/verify/", follow=True), SSO_MESSAGE)
        self.assertEqual(self.web.get("/api/state/").json()["user"]["name"], "Sari UI")
        self.assertEqual(User.objects.count(), 2)

    def test_cross_client_invitation(self):
        self.web.post("/friends/", {"action": "invite", "email": "adi@example.com"})
        person, = self.native.get("/friends/").json()["people"]
        self.assertEqual(person["status"], "Permintaan masuk")
        self.web.post("/friends/", {"action": "accept", "id": person["id"]})
        self.assertContains(self.web.get("/friends/"), "Terkirim")
        self.native.post("/friends/", {"action": "accept", "id": person["id"]})
        self.assertEqual(self.native.get("/friends/").json()["people"][0]["status"], "Friends")
        self.assertContains(self.web.get("/friends/"), "Adi")

    def test_cross_client_meet(self):
        state = self.native.get("/api/state/").json()
        slot = {"date": state["date"], "window": state["window"]}
        rooms = self.native.get("/api/state/", {**slot, "building": "casual", "picker": "1"}).json()["rooms"]
        created = self.web.post("/meets/create/", {**slot, "room": rooms[0]["name"], "title": "Django Discussion",
                                "topic": "WebDev", "join_mode": "approval"})
        self.assertEqual(created.status_code, 201)
        meet, = self.native.get("/api/state/").json()["meets"]
        action = f"/meets/{meet['id']}/action/"
        self.native.post(action, {"action": "join"})
        hosted, = self.web.get("/api/state/").json()["meets"]
        self.web.post(action, {"action": "approve", "member": hosted["requests"][0]["id"]})
        self.assertEqual(self.native.get("/api/state/").json()["meets"][0]["status"], "joined")
        self.assertContains(self.web.get(created.json()["url"]), "Django Discussion")
