import hashlib
import re
import secrets
from datetime import timedelta
from threading import Lock

import firebase_admin
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import GoogleAuthError

from .models import DesktopGrant, StudentProfile
from .profiles import profile_for

_app_lock = Lock()


def config_context(request):
    return {"firebase_web": settings.FIREBASE_WEB}


def verified_identity(token):
    with _app_lock:
        try:
            app = firebase_admin.get_app("nongkee")
        except ValueError:
            app = firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_WEB["projectId"]}, name="nongkee")
    return auth.verify_id_token(token, app=app, check_revoked=True)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@require_GET
@never_cache
def desktop_login(request):
    return render(request, "meets/desktop_login.html")


@require_POST
@never_cache
def exchange(request):
    if not settings.FIREBASE_WEB:
        return JsonResponse({"error": "Google Sign-In belum dikonfigurasi."}, status=503)
    try:
        identity = verified_identity(request.POST.get("token", ""))
    except (auth.CertificateFetchError, GoogleAuthError, OSError):
        return JsonResponse({"error": "Layanan Google belum tersedia. Coba lagi nanti."}, status=503)
    except (ValueError, FirebaseError):
        return JsonResponse({"error": "Sesi Google tidak valid. Silakan masuk kembali."}, status=401)
    email = identity.get("email", "").strip().lower()
    if not (identity.get("email_verified") is True and email and identity.get("firebase", {}).get("sign_in_provider") == "google.com"):
        return JsonResponse({"error": "Gunakan akun Google dengan email terverifikasi."}, status=403)
    challenge = request.POST.get("challenge", "")
    if challenge and not re.fullmatch(r"[a-f0-9]{64}", challenge):
        return JsonResponse({"error": "Permintaan desktop tidak valid."}, status=400)
    linking = request.POST.get("link") == "1"
    try:
        with transaction.atomic():
            match = StudentProfile.objects.select_related("user").filter(firebase_uid=identity["uid"]).first()
            if linking:
                if not request.user.is_authenticated or request.user.email.lower() != email or (match and match.user_id != request.user.pk):
                    return JsonResponse({"error": "Pilih akun Google dengan email yang sama dengan profil Anda."}, status=403)
                person = profile_for(request.user)
                if person.firebase_uid and person.firebase_uid != identity["uid"]:
                    return JsonResponse({"error": "Profil sudah terhubung ke akun Google lain."}, status=409)
                person.firebase_uid = identity["uid"]
                person.save(update_fields=["firebase_uid"])
                user = request.user
            elif match:
                user = match.user
            else:
                if User.objects.filter(email__iexact=email).exists():
                    return JsonResponse({"error": "Email ini sudah terdaftar. Masuk dengan kata sandi, lalu pilih Hubungkan Google di Profil."}, status=409)
                user = User.objects.create_user(username=email if len(email) <= 150 else secrets.token_hex(24),
                                                email=email, first_name=identity.get("name", "")[:150])
                person = profile_for(user)
                person.firebase_uid = identity["uid"]
                person.save(update_fields=["firebase_uid"])
            if not user.is_active:
                return JsonResponse({"error": "Akun tidak aktif."}, status=403)
            if challenge:
                DesktopGrant.objects.filter(expires__lte=timezone.now()).delete()
                code = secrets.token_urlsafe(18)
                DesktopGrant.objects.create(code_hash=digest(code), challenge=challenge, user=user,
                                           expires=timezone.now() + timedelta(minutes=3))
                return JsonResponse({"code": code})
    except IntegrityError:
        return JsonResponse({"error": "Akun sedang diperbarui. Silakan coba masuk kembali."}, status=409)
    login(request, user)
    destination = request.POST.get("next", "/")
    safe = url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure())
    return JsonResponse({"url": destination if safe and destination else "/"})


@require_POST
@never_cache
def redeem(request):
    with transaction.atomic():
        grant = DesktopGrant.objects.select_related("user").filter(code_hash=digest(request.POST.get("code", "")),
                  challenge=digest(request.POST.get("verifier", "")), expires__gt=timezone.now(), user__is_active=True).first()
        if not grant:
            return JsonResponse({"error": "Kode salah atau kedaluwarsa. Mulai lagi dari aplikasi desktop."}, status=403)
        user = grant.user
        grant.delete()
    login(request, user)
    return JsonResponse({"csrf": get_token(request)})

