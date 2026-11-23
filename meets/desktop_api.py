from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import EmailLoginForm, EmailSignupForm, SlotForm
from .models import Meet
from django.conf import settings
from .profiles import profile_data
from .social import name
from .timetable import BUILDINGS, initial_slot, room_options
from .views import active_meet, detail_context, meet_queryset


@require_GET
def state(request):
    date, window = initial_slot()
    if request.GET:
        form = SlotForm(request.GET)
        building = request.GET.get("building", "")
        if not form.is_valid() or building not in dict(BUILDINGS + [("casual", "Casual")]):
            return JsonResponse({"error": "Pilih tanggal Senin–Sabtu dan slot yang valid."}, status=400)
        return JsonResponse({"rooms": room_options(**form.cleaned_data, building=building,
                                                  include_casual=request.GET.get("picker") == "1")})
    user = request.user
    meets = []
    for meet in meet_queryset().filter(date__gte=timezone.localdate()):
        if not active_meet(meet):
            continue
        info = detail_context(meet, user)
        meets.append({
            "id": meet.pk, "title": meet.title, "topic": meet.get_topic_display(), "room": meet.room,
            "date": meet.date, "window": meet.window, "host": name(meet.host), "is_host": info["is_host"],
            "mode": meet.join_mode, "status": info["member"].status if info["member"] else "",
            "attendees": [name(meet.host)] + [name(p.user) for p in info["attendees"]],
            "requests": [{"id": p.pk, "name": name(p.user)} for p in info["pending"]] if info["is_host"] else [],
        })
    return JsonResponse({
        "csrf": get_token(request), "user": profile_data(user) if user.is_authenticated else None, "google_enabled": bool(settings.FIREBASE_WEB),
        "meets": meets, "date": date, "window": window, "windows": Meet.Window.values,
        "topics": Meet.Topic.values, "buildings": BUILDINGS,
    })


@require_POST
def account(request, action):
    if action == "logout":
        logout(request)
    elif action in ("login", "signup"):
        form = EmailSignupForm(request.POST) if action == "signup" else EmailLoginForm(request, data=request.POST)
        if not form.is_valid():
            return JsonResponse({"error": form.errors.as_text()}, status=400)
        login(request, form.save() if action == "signup" else form.get_user())
    else:
        return JsonResponse({"error": "Unknown action"}, status=404)
    return JsonResponse({"csrf": get_token(request)})
