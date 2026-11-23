from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
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



class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", max_length=254)

    def clean_username(self):
        email = self.cleaned_data["username"].lower()
        matches = list(User.objects.filter(email__iexact=email).values_list("username", flat=True)[:2])
        return matches[0] if len(matches) == 1 else ""


class EmailSignupForm(UserCreationForm):
    username = forms.EmailField(label="Email", max_length=150)
    first_name = forms.CharField(label="Nama tampilan", max_length=150)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "first_name")

    def clean_username(self):
        email = self.cleaned_data["username"].lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Email sudah digunakan.")
        return email

    def save(self, commit=True):
        self.instance.email = self.cleaned_data["username"]
        return super().save(commit)
