from datetime import timedelta

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import EmailSignupForm
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import CreateMeetForm, SlotForm
from .models import Meet, Participation, RoomUse
from .timetable import BUILDINGS, DAYS, initial_slot, local_end, local_start, room_keys, room_options, timetable


def meet_queryset():
    return Meet.objects.select_related('host').prefetch_related(
        Prefetch('participants', queryset=Participation.objects.select_related('user')),
    )


def active_meet(meet):
    return local_end(meet.date, meet.window) > timezone.now()


def membership(meet, user):
    return next((member for member in meet.participants.all() if member.user_id == user.pk), None)


def detail_context(meet, user):
    return {
        'meet': meet,
        'attendees': [member for member in meet.participants.all() if member.status == Participation.Status.JOINED],
        'pending': [member for member in meet.participants.all() if member.status == Participation.Status.PENDING],
        'member': membership(meet, user),
        'is_host': meet.host_id == user.pk,
        'active': active_meet(meet),
        'day_label': DAYS[meet.date.weekday()],
    }


@require_GET
def home(request, page='home'):
    date, window = initial_slot()
    today = timezone.localdate()
    days = [today + timedelta(days=offset) for offset in range(7)]
    meet_list = []
    if page != 'rooms_page':
        for meet in meet_queryset().filter(date__gte=today):
            if active_meet(meet):
                details = detail_context(meet, request.user)
                details['avatars'] = [meet.host] + [member.user for member in details['attendees']]
                details['extra'] = max(len(details['avatars']) - 3, 0)
                meet_list.append(details)

    detail = None
    selected = request.GET.get('meet', '')
    if selected.isascii() and selected.isdecimal() and len(selected) <= 18:
        meet = meet_queryset().filter(pk=int(selected)).first()
        if meet:
            detail = detail_context(meet, request.user)

    return render(request, 'meets/home.html', {
        'page': page,
        'meet_list': meet_list,
        'detail': detail,
        'date': date,
        'window': window,
        'day_options': [(day, DAYS[day.weekday()]) for day in days if day.weekday() < len(DAYS)],
        'windows': Meet.Window.choices,
        'topics': Meet.Topic.choices,
        'join_modes': Meet.JoinMode.choices,
        'buildings': BUILDINGS,
    })


@require_GET
@never_cache
def rooms(request):
    form = SlotForm(request.GET)
    building = request.GET.get('building', 'new')
    picker = request.GET.get('picker') == '1'
    allowed = {value for value, _ in BUILDINGS}
    if picker:
        allowed.add('casual')
    if building not in allowed or not form.is_valid():
        return HttpResponseBadRequest('Choose a valid day, time and area.')

    date = form.cleaned_data['date']
    window = form.cleaned_data['window']
    options = room_options(date, window, building, include_casual=picker)
    can_start = local_start(date, window) > timezone.now()
    return render(request, 'meets/room_cards.html', {
        'picker': picker,
        'rooms': options,
        'available': sum(not room['busy'] for room in options) if can_start else 0,
        'window': Meet.Window(window).label,
        'can_start': can_start,
    })


@require_GET
@never_cache
def detail(request, pk):
    meet = get_object_or_404(meet_queryset(), pk=pk)
    return render(request, 'meets/detail.html', {
        'detail': detail_context(meet, request.user),
        'page': request.GET.get('page', 'home'),
    })


@login_required
@require_POST
def create(request):
    form = CreateMeetForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': ' '.join(str(error) for errors in form.errors.values() for error in errors)}, status=400)

    try:
        with transaction.atomic():
            meet = Meet.objects.create(host=request.user, **form.cleaned_data)
            if meet.room in timetable()['academic']:
                RoomUse.objects.bulk_create([
                    RoomUse(meet=meet, room_key=key, date=meet.date, window=meet.window)
                    for key in room_keys(meet.room)
                ])
    except IntegrityError:
        return JsonResponse({'error': 'A meet already uses this classroom at that time. Choose another room.'}, status=409)
    return JsonResponse({'url': f'{reverse("meets:home")}?meet={meet.pk}'}, status=201)


@login_required
@require_POST
def act(request, pk):
    action = request.POST.get('action')
    page = request.POST.get('page')
    destination = reverse(f'meets:{page}' if page in ('mine', 'rooms_page') else 'meets:home')
    with transaction.atomic():
        meet = get_object_or_404(Meet.objects.select_for_update(), pk=pk)
        is_host = meet.host_id == request.user.pk
        if action in ('cancel', 'approve', 'decline') and not is_host:
            return HttpResponseForbidden('Only the host can manage this meet.')
        if action in ('join', 'leave') and is_host:
            return HttpResponseBadRequest('The host is already part of this meet.')

        if action == 'cancel':
            meet.delete()
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'done': True})
            return redirect(destination)
        if action in ('join', 'approve') and not active_meet(meet):
            return HttpResponseBadRequest('This meet has ended.')
        if action == 'join':
            status = Participation.Status.JOINED if meet.join_mode == Meet.JoinMode.DIRECT else Participation.Status.PENDING
            Participation.objects.get_or_create(meet=meet, user=request.user, defaults={'status': status})
        elif action == 'leave':
            Participation.objects.filter(meet=meet, user=request.user).delete()
        elif action in ('approve', 'decline'):
            member_id = request.POST.get('member', '')
            if not (member_id.isascii() and member_id.isdecimal() and len(member_id) <= 18):
                return HttpResponseBadRequest('Choose a valid join request.')
            member = get_object_or_404(Participation, pk=int(member_id), meet=meet, status=Participation.Status.PENDING)
            if action == 'approve':
                member.status = Participation.Status.JOINED
                member.save(update_fields=['status'])
            else:
                member.delete()
        else:
            return HttpResponseBadRequest('Unknown meet action.')

    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'done': True})
    return redirect(f'{destination}?meet={pk}')


@require_http_methods(['GET', 'POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('meets:home')
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = ''
    form = EmailSignupForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect(next_url or 'meets:home')
    return render(request, 'meets/auth.html', {'form': form, 'signup': True, 'next': next_url})

