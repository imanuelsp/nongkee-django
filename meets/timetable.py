import json
import re
from datetime import datetime, time, timedelta
from functools import cache
from pathlib import Path

from django.utils import timezone

from .models import Meet, RoomUse

DAYS = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu')
BUILDINGS = [('new', 'Gedung Baru'), ('old', 'Gedung Lama'), ('lab', 'Lab'), ('', 'Semua')]
TIMETABLE = Path(__file__).with_name('data') / 'timetable.json'
ROOM_CODE = re.compile(r'\bA\d\.\d{2}\b')


@cache
def timetable():
    with TIMETABLE.open(encoding='utf-8') as source:
        return json.load(source)


def room_keys(room):
    # A combined lab shares its individual rooms with other timetable entries.
    return tuple(sorted(set(ROOM_CODE.findall(room)))) or (room,)


def local_time(date, value):
    return timezone.make_aware(datetime.combine(date, time.fromisoformat(value)))


def local_start(date, window):
    return local_time(date, window.split('-')[0])


def local_end(date, window):
    return local_time(date, window.split('-')[1])


def initial_slot():
    now = timezone.localtime()
    date = now.date()
    if date.weekday() < len(DAYS):
        for window in Meet.Window.values:
            if local_start(date, window) > now:
                return date, window
    date += timedelta(days=1)
    if date.weekday() == 6:
        date += timedelta(days=1)
    return date, Meet.Window.MORNING


def scheduled_classes(date, window):
    start, end = window.split('-')
    day = DAYS[date.weekday()]
    return {
        key: entry
        for entry in timetable()['classes']
        if entry['day'] == day and entry['start_time'] < end and entry['end_time'] > start
        for key in room_keys(entry['room'])
    }


def room_options(date, window, building, include_casual=False):
    data = timetable()
    classes = scheduled_classes(date, window)
    meet_rooms = dict(RoomUse.objects.filter(date=date, window=window).values_list('room_key', 'meet__title'))
    rooms = []
    for name in data['academic']:
        normalized = name.lower().replace('.', '')
        in_building = {
            'new': 'ged baru' in normalized or 'gd baru' in normalized,
            'old': 'gd lama' in normalized or 'ged lama' in normalized,
            'lab': 'lab' in normalized,
            '': True,
        }
        if in_building.get(building):
            keys = room_keys(name)
            entry = next((classes[key] for key in keys if key in classes), None)
            meet_title = next((meet_rooms[key] for key in keys if key in meet_rooms), '')
            rooms.append({'name': name, 'class': entry, 'meet': meet_title, 'busy': bool(entry or meet_title)})
    if include_casual and building in ('', 'casual'):
        rooms.extend({'name': name, 'casual': True, 'busy': False} for name in data['casual'])
    return sorted(rooms, key=lambda room: (room['busy'], room['name'].casefold()))
