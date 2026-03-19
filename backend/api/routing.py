from django.urls import re_path
from .consumers import CVFeedConsumer

websocket_urlpatterns = [
    re_path(r'ws/cv-feed/$', CVFeedConsumer.as_asgi()),
]
