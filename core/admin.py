from django.contrib import admin
from .models import Project, Task, Workspace
admin.site.register([Project, Workspace])


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(project_id__isnull=False)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "project":
            kwargs["required"] = True
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.site_header = "Közös adminisztráció"
