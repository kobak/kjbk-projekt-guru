from django.contrib import admin
from .models import Project, Task, Workspace
admin.site.register([Project, Task, Workspace])
admin.site.site_header = "Közös adminisztráció"
