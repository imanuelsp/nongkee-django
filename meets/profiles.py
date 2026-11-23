import base64
from datetime import timedelta
from functools import cache
from io import BytesIO
from uuid import uuid4

from django import forms
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import StudentProfile
from .timetable import DAYS, timetable


@cache
def catalogue():
    classes = {}
    for row in timetable()["classes"]:
        label = f"{row['course_name']} · {row['class_name']}"
        classes.setdefault(label, []).append(row)
    return dict(sorted(classes.items()))


def profile_for(user):
    return StudentProfile.objects.defer("avatar").get_or_create(user=user)[0]


def photo_url(profile):
    return reverse("meets:avatar", args=[profile.avatar_key]) if profile.avatar_key else ""


def next_class(classes):
    now = timezone.localtime()
    upcoming = []
    for label in classes:
        for row in catalogue().get(label, []):
            days = (DAYS.index(row["day"]) - now.weekday()) % 7
            if days == 0 and row["start_time"] <= now.strftime("%H:%M"):
                days = 7
            upcoming.append((days, row["start_time"], label, row["room"]))
    if upcoming:
        days, start, label, room = min(upcoming)
        return {"label": label, "date": (now.date() + timedelta(days=days)).isoformat(),
                "time": start, "room": room}


def profile_data(user):
    profile = profile_for(user)
    return {"name": user.first_name or profile.handle, "email": user.email,
            "handle": profile.handle, "avatar": photo_url(profile), "classes": profile.classes,
            "interests": profile.interests, "next_class": next_class(profile.classes)}


def thumbnail(raw):
    try:
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError
        with Image.open(BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > 12_000_000:
                raise ValueError
            preview = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (144, 144), Image.Resampling.LANCZOS)
            output = BytesIO()
            preview.save(output, "PNG")
            return output.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise forms.ValidationError("Pilih JPEG, PNG, atau WebP hingga 2 MB dan 12 megapiksel.") from exc


class StudentForm(forms.Form):
    first_name = forms.CharField(label="Nama tampilan", max_length=150)
    handle = forms.RegexField(label="Username", regex=r"^[a-zA-Z0-9_]{3,30}$", max_length=30,
                              help_text="3–30 huruf, angka, atau garis bawah.")
    classes = forms.MultipleChoiceField(label="Kelas saya", required=False)
    interests = forms.CharField(label="Minat", required=False, max_length=350,
                                help_text="Pisahkan dengan koma, misalnya UI Design, Basket, Python.")
    photo = forms.FileField(label="Ganti foto", required=False, widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}))
    remove_photo = forms.BooleanField(label="Hapus foto", required=False)

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, initial={"first_name": profile.user.first_name or profile.handle, "handle": profile.handle,
                         "classes": profile.classes, "interests": ", ".join(profile.interests)}, **kwargs)
        self.fields["classes"].choices = [(c, c) for c in sorted(set(catalogue()) | set(profile.classes))]

    def clean_handle(self):
        handle = self.cleaned_data["handle"].lower()
        if StudentProfile.objects.filter(handle=handle).exclude(pk=self.profile.pk).exists():
            raise forms.ValidationError("Username ini sudah digunakan.")
        return handle

    def clean_interests(self):
        values = {}
        for value in self.cleaned_data["interests"].split(","):
            value = " ".join(value.split())
            if value:
                values.setdefault(value.casefold(), value)
        if len(values) > 10 or any(len(v) > 30 for v in values.values()):
            raise forms.ValidationError("Tambahkan hingga 10 minat, maksimal 30 karakter per minat.")
        return list(values.values())

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            return thumbnail(photo.read(2 * 1024 * 1024 + 1))
        encoded = self.data.get("photo_base64")
        if encoded:
            try:
                raw = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise forms.ValidationError("Foto tidak valid.") from exc
            return thumbnail(raw)

    def save(self):
        data = self.cleaned_data
        profile = self.profile
        profile.handle = data["handle"]
        profile.classes = list(dict.fromkeys(data["classes"]))
        profile.interests = data["interests"]
        fields = ["handle", "classes", "interests"]
        if data["photo"] or data["remove_photo"]:
            profile.avatar = data["photo"] or b""
            profile.avatar_key = uuid4() if profile.avatar else None
            fields += ["avatar", "avatar_key"]
        profile.save(update_fields=fields)
        profile.user.first_name = data["first_name"]
        profile.user.save(update_fields=["first_name"])

