from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views, social, desktop_api, google_auth
from .forms import EmailLoginForm

app_name = 'meets'

urlpatterns = [
    path('auth/google/', google_auth.exchange, name='google'),
    path('auth/desktop/', google_auth.desktop_login),
    path('auth/desktop/redeem/', google_auth.redeem),
    path('avatars/<uuid:key>/', social.avatar, name='avatar'),
    path('api/state/', desktop_api.state),
    path('api/account/<str:action>/', desktop_api.account),
    path('friends/', social.friends, name='friends'),
    path('profile/', social.profile, name='profile'),
    path('profile/verify/', social.verify, name='verify'),
    path('', views.home, name='home'),
    path('my-meets/', RedirectView.as_view(pattern_name='meets:friends'), name='mine'),
    path('rooms/', views.home, {'page': 'rooms_page'}, name='rooms_page'),
    path('rooms/options/', views.rooms, name='room_options'),
    path('meets/create/', views.create, name='create'),
    path('meets/<int:pk>/', views.detail, name='detail'),
    path('meets/<int:pk>/action/', views.act, name='act'),
    path('login/', auth_views.LoginView.as_view(authentication_form=EmailLoginForm, template_name='meets/auth.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
]
