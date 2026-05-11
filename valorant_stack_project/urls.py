from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from dotenv import load_dotenv
import os

load_dotenv()

handler404 = 'valorant_stack_app.views.custom_404'

# Environment-based admin URL
if settings.DEBUG:
    admin_url = 'admin/'
else:
    admin_url = os.getenv('ADMIN_URL')

urlpatterns = [
    path(admin_url, admin.site.urls),
    path('', include('valorant_stack_app.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
