from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include, re_path
from core import views, mcp
from core.oauth import MCPAuthorizationView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="login.html")),
    path("oauth/register/", mcp.register),
    path("oauth/authorize/", MCPAuthorizationView.as_view()),
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path(".well-known/oauth-authorization-server", mcp.metadata),
    path(".well-known/oauth-protected-resource", mcp.metadata, {"resource": True}),
    path(".well-known/oauth-protected-resource/mcp", mcp.metadata, {"resource": True}),
    path("mcp", mcp.endpoint),
    path("health/", views.health), path("sw.js", views.service_worker),
    path("api/session/", views.session), path("api/login/", views.login), path("api/logout/", views.logout),
    path("api/profile/", views.profile), path("api/bootstrap/", views.bootstrap),
    path("api/appearance/", views.appearance),
    path("api/mcp/connections/", views.mcp_connections),
    path("api/projects/", views.projects), path("api/projects/<uuid:project_id>/", views.projects),
    path("api/tasks/", views.create_task), path("api/tasks/<uuid:task_id>/", views.task),
    path("api/tasks/<uuid:task_id>/comments/", views.comments),
    path("api/tasks/<uuid:task_id>/checklist/", views.checklist),
    path("api/tasks/<uuid:task_id>/checklist/<int:item_id>/", views.checklist),
    path("api/tasks/<uuid:task_id>/attachments/", views.attachments),
    path("api/attachments/<int:attachment_id>/download/", views.attachment),
    path("api/attachments/<int:attachment_id>/", views.attachment),
    path("api/notifications/read/", views.read_notifications), path("api/push/", views.push_subscription),
    path("api/notification-preferences/", views.notification_preferences),
    path("api/invites/", views.invites), path("api/invites/<str:token>/", views.accept_invite),
    path("api/members/<int:user_id>/", views.member_email),
    path("api/members/<int:user_id>/deactivate/", views.deactivate_member),
    path("api/google/connect/", views.google_start), path("api/google/callback/", views.google_callback),
    path("api/google/disconnect/", views.google_disconnect), path("api/tasks/<uuid:task_id>/calendar/", views.task_calendar),
    path("api/tasks/<uuid:task_id>/calendar.ics", views.task_calendar_file),
    re_path(r"^(?P<path>.*)$", views.spa),
]
