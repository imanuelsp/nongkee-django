from django import forms
from django.utils import timezone

from .models import Meet
from .timetable import DAYS, local_start, room_keys, scheduled_classes, timetable


class SlotForm(forms.Form):
    date = forms.DateField(input_formats=['%Y-%m-%d'])
    window = forms.ChoiceField(choices=Meet.Window.choices)

    def clean_date(self):
        date = self.cleaned_data['date']
        if date.weekday() >= len(DAYS):
            raise forms.ValidationError('Choose a day from Monday through Saturday.')
        return date


class CreateMeetForm(SlotForm):
    title = forms.CharField(max_length=100)
    topic = forms.ChoiceField(choices=Meet.Topic.choices)
    join_mode = forms.ChoiceField(choices=Meet.JoinMode.choices)
    room = forms.CharField(max_length=140)

    def clean_room(self):
        room = self.cleaned_data['room']
        data = timetable()
        if room not in data['academic'] and room not in data['casual']:
            raise forms.ValidationError('Select a room or casual spot from the list.')
        return room

    def clean(self):
        cleaned = super().clean()
        date, window, room = (cleaned.get(field) for field in ('date', 'window', 'room'))
        if date and window:
            if local_start(date, window) <= timezone.now():
                self.add_error('date', 'Choose a time slot that has yet to start.')
            elif room in timetable()['academic']:
                occupied = scheduled_classes(date, window)
                if any(key in occupied for key in room_keys(room)):
                    self.add_error('room', 'A class is scheduled in that room during this time.')
        return cleaned
