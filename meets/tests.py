from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

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
        profile = self.web.get("/profile/")
        self.assertFalse(profile.context["form"].is_bound)
        self.assertContains(profile, "Belum terverifikasi")
        self.web.post("/profile/", {"first_name": "Sari UI", "verified": "true"})
        self.assertContains(self.web.post("/profile/verify/", follow=True), SSO_MESSAGE)
        self.assertEqual(self.web.get("/api/state/").json()["user"]["name"], "Sari UI")
        self.assertEqual(User.objects.count(), 2)

    def test_cross_client_invitation(self):
        from .profiles import catalogue
        course = next(iter(catalogue()))
        self.native.post("/profile/", {"first_name": "Adi", "handle": "adi123", "classes": course, "interests": "Python"})
        self.web.post("/profile/", {"first_name": "Sari", "classes": course, "interests": "python, Basket"})
        self.web.post("/friends/", {"action": "invite", "handle": "@ADI123"})
        person, = self.native.get("/friends/").json()["people"]
        self.assertEqual(person["status"], "Permintaan masuk")
        self.assertEqual(person["shared_classes"], [course])
        self.assertEqual(person["shared_interests"], ["python"])
        self.assertContains(self.web.get("/friends/"), "This person is in your class")
        self.assertTrue(self.web.get("/api/state/").json()["user"]["next_class"])
        self.assertEqual(self.native.post("/profile/", {"first_name": "Adi", "handle": self.web.get("/api/state/").json()["user"]["handle"]}).status_code, 400)
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

    def test_photo_upload_and_remove(self):
        image = BytesIO()
        Image.new("RGB", (200, 250)).save(image, "JPEG")
        upload = SimpleUploadedFile("portrait.jpg", image.getvalue(), content_type="image/jpeg")
        result = self.native.post("/profile/", {"first_name": "Adi", "photo": upload})
        avatar = result.json()["avatar"]
        self.assertEqual(Image.open(BytesIO(self.native.get(avatar).content)).size, (144, 144))
        invalid = self.native.post("/profile/", {"first_name": "Adi", "photo_base64": "Zm9v"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.native.get(avatar).status_code, 200)
        self.native.post("/profile/", {"first_name": "Adi", "remove_photo": "on"})
        self.assertEqual(self.native.get(avatar).status_code, 404)

    @override_settings(FIREBASE_WEB={"projectId": "test"})
    @patch("meets.google_auth.verified_identity")
    def test_google_existing_account_and_desktop(self, verify):
        from .google_auth import digest
        verify.return_value = {"uid": "uid-sari", "email": "sari@example.com", "email_verified": True,
                               "firebase": {"sign_in_provider": "google.com"}}
        guest = Client()
        self.assertEqual(guest.post("/auth/google/", {"token": "mock"}).status_code, 409)
        self.assertEqual(self.web.post("/auth/google/", {"token": "mock", "link": "1"}).status_code, 200)
        self.assertEqual(guest.post("/auth/google/", {"token": "mock"}).status_code, 200)
        code = guest.post("/auth/google/", {"token": "mock", "challenge": digest("device-key")}).json()["code"]
        self.assertEqual(self.native.post("/auth/desktop/redeem/", {"code": code, "verifier": "other"}).status_code, 403)
        params = {"code": code, "verifier": "device-key"}
        self.assertEqual(self.native.post("/auth/desktop/redeem/", params).status_code, 200)
        self.assertEqual(self.native.post("/auth/desktop/redeem/", params).status_code, 403)
        self.assertEqual(self.native.get("/api/state/").json()["user"]["email"], "sari@example.com")
        verify.return_value["email_verified"] = False
        self.assertEqual(guest.post("/auth/google/", {"token": "mock"}).status_code, 403)
        verify.side_effect = ValueError("invalid token")
        self.assertEqual(guest.post("/auth/google/", {"token": "mock"}).status_code, 401)

    @override_settings(FIREBASE_WEB={"projectId": "test"})
    @patch("meets.google_auth.verified_identity")
    def test_new_google_account_keeps_uid_and_student_status(self, verify):
        verify.return_value = {"uid": "new-google-id", "email": "lina@example.com", "name": "Lina",
                               "email_verified": True, "firebase": {"sign_in_provider": "google.com"}}
        guest = Client()
        for _ in range(2):
            self.assertEqual(guest.post("/auth/google/", {"token": "mock", "next": "https://example.org"}).json()["url"], "/")
        self.assertEqual(User.objects.filter(email="lina@example.com").count(), 1)
        self.assertContains(guest.get("/profile/"), "Belum terverifikasi")

    def test_same_course_different_section_has_no_badge(self):
        from .profiles import catalogue
        groups = {}
        for label in catalogue():
            groups.setdefault(label.split(" · ")[0], []).append(label)
        a, b = next(labels[:2] for labels in groups.values() if len(labels) > 1)
        self.native.post("/profile/", {"first_name": "Adi", "handle": "adi123", "classes": a})
        self.web.post("/profile/", {"first_name": "Sari", "classes": b})
        self.web.post("/friends/", {"action": "invite", "handle": "adi123"})
        self.assertNotContains(self.web.get("/friends/"), "This person is in your class")
