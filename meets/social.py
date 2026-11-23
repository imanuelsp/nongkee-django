from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import FriendRequest, StudentProfile
from .profiles import StudentForm, catalogue, photo_url, profile_data, profile_for

SSO_MESSAGE = "SSO UI belum terhubung. Status mahasiswa Anda masih Belum terverifikasi."


def wants_json(request):
    return request.headers.get("Accept") == "application/json"


def name(user):
    return user.first_name or user.username.split("@")[0]


def connections(user):
    own = profile_for(user)
    rows = FriendRequest.objects.filter(Q(sender=user) | Q(recipient=user)).select_related(
        "sender__student", "recipient__student").defer("sender__student__avatar", "recipient__student__avatar")
    people = []
    for row in rows.order_by("-pk"):
        other = row.recipient if row.sender_id == user.pk else row.sender
        peer = other.student
        people.append({"id": row.pk, "name": name(other), "handle": peer.handle, "avatar": photo_url(peer),
                       "shared_classes": sorted(set(peer.classes).intersection(own.classes)),
                       "shared_interests": [i for i in peer.interests if i.casefold() in {s.casefold() for s in own.interests}],
                       "status": "Friends" if row.accepted else "Terkirim" if row.sender_id == user.pk else "Permintaan masuk"})
    return people


@require_GET
def avatar(request, key):
    profile = get_object_or_404(StudentProfile.objects.only("avatar"), avatar_key=key)
    return HttpResponse(bytes(profile.avatar), content_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    person = profile_for(request.user)
    if request.method == "GET" and wants_json(request):
        return JsonResponse({"user": profile_data(request.user), "catalogue": list(catalogue())})
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None:
        # Earlier clients only send the display name.
        data.setdefault("handle", person.handle)
        data.setdefault("interests", ", ".join(person.interests))
        if "classes" not in data and "classes_present" not in data:
            data.setlist("classes", person.classes)
    form = StudentForm(data, request.FILES if data is not None else None, profile=person)
    if data is not None and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error("handle", "Username ini sudah digunakan.")
        else:
            if wants_json(request):
                return JsonResponse(profile_data(request.user))
            messages.success(request, "Profil tersimpan.")
            return redirect("meets:profile")
    if data is not None and wants_json(request):
        return JsonResponse({"error": form.errors.as_text()}, status=400)
    return render(request, "meets/profile.html", {"form": form, "person": profile_data(request.user)})


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
        action = request.POST.get("action")
        with transaction.atomic():
            if action == "invite":
                handle = request.POST.get("handle", "").strip().lstrip("@").lower()
                peer = StudentProfile.objects.filter(handle=handle, user__is_active=True).only("user_id").first()
                if not peer or peer.user_id == request.user.pk:
                    error = "Masukkan username akun Nongkee lain yang terdaftar."
                elif FriendRequest.objects.filter(sender_id=peer.user_id, recipient=request.user).exists():
                    error = "Periksa daftar Friends untuk hubungan yang sudah ada."
                else:
                    FriendRequest.objects.get_or_create(sender=request.user, recipient_id=peer.user_id)
            elif action in ("accept", "dismiss"):
                key = request.POST.get("id", "")
                rows = FriendRequest.objects.filter(pk=int(key), accepted=False) if key.isascii() and key.isdecimal() and len(key) <= 18 else FriendRequest.objects.none()
                if action == "accept":
                    changed = rows.filter(recipient=request.user).update(accepted=True)
                else:
                    changed, _ = rows.filter(Q(sender=request.user) | Q(recipient=request.user)).delete()
                if not changed:
                    error = "Permintaan tidak ditemukan."
            else:
                error = "Tindakan tidak dikenal."
        if not error and not wants_json(request):
            messages.success(request, {"invite": "Undangan terkirim.", "accept": "Teman ditambahkan.", "dismiss": "Undangan ditutup."}[action])
            return redirect("meets:friends")
    people = connections(request.user)
    if wants_json(request):
        return JsonResponse({"people": people, "error": error}, status=400 if error else 200)
    return render(request, "meets/home.html", {"page": "friends", "people": people, "friend_error": error})
