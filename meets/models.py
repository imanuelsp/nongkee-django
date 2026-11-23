from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Meet(models.Model):
    class Topic(models.TextChoices):
        STUDIES = 'Pacillian Studies', 'Pacillian Studies'
        WEB = 'WebDev', 'WebDev'
        GAME = 'GameDev', 'GameDev'
        AI = 'AI / ML', 'AI / ML'
        MANBIS = 'MANBIS', 'MANBIS'
        CASUAL = 'Casual', 'Casual Nongkee'

    class JoinMode(models.TextChoices):
        DIRECT = 'direct', 'Anyone can join'
        APPROVAL = 'approval', 'Host approves requests'

    class Window(models.TextChoices):
        MORNING = '08:00-10:00', '08:00 - 10:00'
        LATE_MORNING = '10:00-12:00', '10:00 - 12:00'
        EARLY_AFTERNOON = '13:00-15:00', '13:00 - 15:00'
        LATE_AFTERNOON = '15:00-17:00', '15:00 - 17:00'

    title = models.CharField(max_length=100)
    topic = models.CharField(max_length=24, choices=Topic.choices)
    join_mode = models.CharField(max_length=8, choices=JoinMode.choices, default=JoinMode.DIRECT)
    date = models.DateField()
    window = models.CharField(max_length=11, choices=Window.choices)
    room = models.CharField(max_length=140)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_meets')

    class Meta:
        ordering = ['date', 'window', 'pk']

    def __str__(self):
        return self.title


class RoomUse(models.Model):
    meet = models.ForeignKey(Meet, on_delete=models.CASCADE, related_name='room_uses')
    room_key = models.CharField(max_length=140)
    date = models.DateField()
    window = models.CharField(max_length=11, choices=Meet.Window.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['date', 'window', 'room_key'], name='unique_classroom_slot')]


class Participation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        JOINED = 'joined', 'Joined'

    meet = models.ForeignKey(Meet, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=7, choices=Status.choices)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['meet', 'user'], name='unique_meet_participant')]

class FriendRequest(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invites")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_invites")
    accepted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sender", "recipient"], name="unique_friend_invite"),
        ]


def new_handle():
    return "nongkee_" + uuid4().hex[:12]


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student")
    handle = models.CharField(max_length=30, unique=True, default=new_handle)
    classes = models.JSONField(default=list)
    interests = models.JSONField(default=list)
    avatar = models.BinaryField(default=bytes)
    avatar_key = models.UUIDField(null=True, unique=True)
    firebase_uid = models.CharField(max_length=128, null=True, unique=True)


class DesktopGrant(models.Model):
    code_hash = models.CharField(max_length=64, primary_key=True)
    challenge = models.CharField(max_length=64)
    expires = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)



@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_student_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        StudentProfile.objects.get_or_create(user=instance)
