from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProfileForm
from .models import FriendRequest

SSO_MESSAGE = "SSO UI belum terhubung. Status mahasiswa Anda masih Belum terverifikasi."


def wants_json(request):
    return request.headers.get("Accept") == "application/json"


def name(user):
    return user.first_name or user.username.split("@")[0]


def connections(user):
    rows = FriendRequest.objects.filter(Q(sender=user) | Q(recipient=user)).select_related("sender", "recipient")
    return [
        {"id": row.pk, "name": name(row.recipient if row.sender_id == user.pk else row.sender),
         "status": "Friends" if row.accepted else "Terkirim" if row.sender_id == user.pk else "Permintaan masuk"}
        for row in rows.order_by("pk")
    ]


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            if wants_json(request):
                return JsonResponse({"name": name(request.user)})
            messages.success(request, "Profil tersimpan.")
            return redirect("meets:profile")
        if wants_json(request):
            return JsonResponse({"error": form.errors.as_text()}, status=400)
    return render(request, "meets/profile.html", {"form": form})


@login_required
@require_POST
def verify(request):
    if wants_json(request):
        return JsonResponse({"message": SSO_MESSAGE})
    messages.info(request, SSO_MESSAGE)
    return redirect("meets:profile")


@login_required
@require_http_methods(["GET", "POST"])
def friends(request):
    error = ""
    if request.method == "POST":
        with transaction.atomic():
            if request.POST.get("action") == "invite":
                matches = list(User.objects.filter(email__iexact=request.POST.get("email", "").strip(), is_active=True)[:2])
                if len(matches) != 1 or matches[0] == request.user:
                    error = "Pilih email akun Nongkee lain yang terdaftar."
                elif FriendRequest.objects.filter(sender=matches[0], recipient=request.user).exists():
                    error = "Hubungan sudah ada. Periksa daftar Friends."
                else:
                    FriendRequest.objects.get_or_create(sender=request.user, recipient=matches[0])
            elif request.POST.get("action") == "accept":
                key = request.POST.get("id", "")
                if not (key.isascii() and key.isdecimal() and len(key) <= 18 and
                        FriendRequest.objects.filter(pk=int(key), recipient=request.user).update(accepted=True)):
                    error = "Permintaan tidak ditemukan."
            else:
                error = "Tindakan tidak dikenal."
        if not error and not wants_json(request):
            return redirect("meets:friends")
    people = connections(request.user)
    if wants_json(request):
        return JsonResponse({"people": people, "error": error}, status=400 if error else 200)
    return render(request, "meets/home.html", {"page": "friends", "people": people, "friend_error": error})
