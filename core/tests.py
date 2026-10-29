import base64
import hashlib
import json
import tempfile
from datetime import date, time, timedelta
from urllib.parse import urlencode, urlparse, parse_qs
from unittest.mock import patch, Mock
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, RequestFactory, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application
from .models import Project, Task, Workspace, Notification, GoogleConnection, CalendarLink, Invite
from .services import save_task
from .calendar import event_payload, sync_link, cipher, event_dates, calendar_file, template_url
from .worker import tick

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False)
class AppTests(TestCase):
    def setUp(self):
        Workspace.objects.create(id=1)
        self.admin = User.objects.create_user(username="admin@example.com", email="admin@example.com", password="My-test-password-2026!", first_name="Admin", is_staff=True)
        self.member = User.objects.create_user(username="member@example.com", email="member@example.com", password="My-test-password-2026!", first_name="Tag")
        self.project = Project.objects.create(name="Tesztprojekt")
        self.task = save_task({"project_id": str(self.project.id), "title": "Közös feladat", "assignee_id": self.member.id, "due_date": "2026-10-27"}, self.admin)
        self.client.force_login(self.admin, backend="django.contrib.auth.backends.ModelBackend")
    def post(self, path, data=None, method="post", client=None):
        return getattr(client or self.client, method)(path, json.dumps(data or {}), content_type="application/json")
    def test_authentication_required_for_workspace_and_downloads(self):
        anon=Client()
        self.assertEqual(anon.get("/api/bootstrap/").status_code,401)
        self.assertEqual(anon.get("/api/attachments/1/download/").status_code,401)
    def test_shared_data_visible_to_other_member(self):
        self.client.force_login(self.member)
        result=self.client.get("/api/bootstrap/").json()
        self.assertEqual(result["tasks"][0]["title"],self.task.title)
        self.assertEqual(len(result["projects"]),1)
    def test_session_login_logout_and_csrf(self):
        client=Client(enforce_csrf_checks=True)
        token=client.get("/api/session/").json()["csrf"]
        self.assertEqual(self.post("/api/login/",{"email":self.admin.email,"password":"My-test-password-2026!"},client=client).status_code,403)
        response=client.post("/api/login/",json.dumps({"email":self.admin.email,"password":"My-test-password-2026!"}),content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["user"]["id"],self.admin.id)
        self.assertNotEqual(token,response.json()["csrf"])
    def test_create_update_and_conflict_prevents_overwrite(self):
        path=f"/api/tasks/{self.task.id}/"
        first=self.post(path,{"version":1,"title":"Új cím"},"patch")
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json()["task"]["version"],2)
        stale=self.post(path,{"version":1,"title":"Elavult cím"},"patch")
        self.assertEqual(stale.status_code,409)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title,"Új cím")
    def test_validation_rejects_time_without_date_and_unknown_member(self):
        for patch_data in [{"due_time":"10:00","due_date":None},{"assignee_id":999999},{"status":"magic"},{"labels":"not-a-list"}]:
            r=self.post(f"/api/tasks/{self.task.id}/",{"version":1,**patch_data},"patch")
            self.assertEqual(r.status_code,400)
    def test_archived_project_cannot_be_edited(self):
        self.project.archived=True;self.project.save()
        r=self.post(f"/api/tasks/{self.task.id}/",{"version":1,"title":"Tiltott"},"patch")
        self.assertEqual(r.status_code,400)
    def test_assignment_and_comments_notify_only_others(self):
        self.assertEqual(Notification.objects.filter(user=self.member).count(),1)
        self.post(f"/api/tasks/{self.task.id}/comments/",{"body":"Megjegyzés"})
        self.assertEqual(Notification.objects.filter(user=self.member).count(),2)
        self.assertEqual(Notification.objects.filter(user=self.admin).count(),0)
    def test_cannot_mark_other_users_notifications_read(self):
        n=Notification.objects.get(user=self.member)
        self.post("/api/notifications/read/",{"id":n.id})
        n.refresh_from_db();self.assertFalse(n.read)
    def test_checklist_stays_with_its_task(self):
        response=self.post(f"/api/tasks/{self.task.id}/checklist/",{"text":"Első lépés"})
        self.assertEqual(response.status_code,200)
        item=self.task.checklist.get()
        other=save_task({"project_id":str(self.project.id),"title":"Másik"},self.admin)
        r=self.post(f"/api/tasks/{other.id}/checklist/{item.id}/",{"done":True},"patch")
        self.assertEqual(r.status_code,404)
    def test_uploaded_files_require_login_and_force_download(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            r=self.client.post(f"/api/tasks/{self.task.id}/attachments/",{"file":SimpleUploadedFile("teszt.html",b"<script>alert(1)</script>","text/html")})
            self.assertEqual(r.status_code,200)
            a=self.task.attachments.get()
            download=self.client.get(f"/api/attachments/{a.id}/download/")
            self.assertEqual(download["Content-Type"],"application/octet-stream")
            self.assertIn("attachment",download["Content-Disposition"])
            self.assertEqual(Client().get(f"/api/attachments/{a.id}/download/").status_code,401)
            self.assertEqual(b"".join(download.streaming_content),b"<script>alert(1)</script>")
    def test_invite_single_use_and_no_public_registration(self):
        r=self.post("/api/invites/",{"email":"new@example.com"})
        self.assertEqual(r.status_code,200)
        raw=parse_qs(urlparse(r.json()["url"]).query)["invite"][0]
        self.assertNotEqual(Invite.objects.get().token_hash,raw)
        anon=Client()
        result=self.post(f"/api/invites/{raw}/",{"name":"Új tag","password":"Another-test-secret-2026!"},client=anon)
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.post(f"/api/invites/{raw}/",{"name":"Másik","password":"Another-test-secret-2026!"},client=Client()).status_code,404)
    def test_non_admin_cannot_invite_or_deactivate(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post("/api/invites/",{"email":"new@example.com"}).status_code,403)
        self.assertEqual(self.post(f"/api/members/{self.admin.id}/deactivate/").status_code,403)
    def test_workspace_five_member_limit(self):
        for i in range(3):User.objects.create_user(username=f"p{i}@example.com")
        self.assertEqual(self.post("/api/invites/",{"email":"sixth@example.com"}).status_code,400)
    def test_soft_delete_queues_calendar_cleanup(self):
        link=CalendarLink.objects.create(task=self.task,user=self.admin,event_id="ktest",synced_version=1)
        r=self.post(f"/api/tasks/{self.task.id}/",{"version":1},"delete")
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get(f"/api/tasks/{self.task.id}/").status_code,404)
        link.refresh_from_db();self.assertFalse(link.enabled)
    def test_google_callback_requires_matching_state(self):
        response=self.client.get("/api/google/callback/?state=wrong&code=not-real")
        self.assertIn("state_error",response["Location"])
        self.assertFalse(GoogleConnection.objects.exists())
    def test_calendar_all_day_has_exclusive_end_date(self):
        payload=event_payload(self.task)
        self.assertEqual(payload["start"],{"date":"2026-10-27"})
        self.assertEqual(payload["end"],{"date":"2026-10-28"})
    def test_manual_calendar_requires_no_google_connection(self):
        detail=self.client.get(f"/api/tasks/{self.task.id}/").json()["task"]
        query=parse_qs(urlparse(detail["calendar_manual_url"]).query)
        self.assertEqual(query["action"],["TEMPLATE"])
        self.assertEqual(query["dates"],["20261027/20261028"])
        self.assertIsNone(detail["calendar"])
        self.assertFalse(GoogleConnection.objects.exists())
    def test_ics_download_is_authenticated_and_preserves_dates(self):
        path=f"/api/tasks/{self.task.id}/calendar.ics"
        self.assertEqual(Client().get(path).status_code,401)
        r=self.client.get(path)
        self.assertEqual(r.status_code,200)
        self.assertIn("text/calendar",r["Content-Type"])
        self.assertIn(b"DTSTART;VALUE=DATE:20261027\r\n",r.content)
        self.assertIn(b"DTEND;VALUE=DATE:20261028\r\n",r.content)
    def test_ics_folds_utf8_and_escapes_multiline_content(self):
        self.task.title="Ő"*120
        self.task.description="első, második; harmadik\nBEGIN:VEVENT"
        content=calendar_file(self.task)
        self.assertTrue(all(len(line.encode())<=75 for line in content.split("\r\n")))
        unfolded=content.replace("\r\n ","")
        self.assertIn("SUMMARY:"+self.task.title,unfolded)
        self.assertIn("első\\, második\\; harmadik\\nBEGIN:VEVENT",unfolded)
    def test_manual_timed_calendar_uses_utc_with_dst(self):
        self.task.due_date=date(2026,7,15);self.task.due_time=time(14,30)
        self.assertEqual(event_dates(self.task),("20260715T123000Z","20260715T130000Z"))
    def test_calendar_timed_event_uses_budapest_dst(self):
        self.task.due_date=date(2026,7,15);self.task.due_time=time(14,30)
        payload=event_payload(self.task)
        self.assertEqual(payload["start"]["dateTime"],"2026-07-15T14:30:00+02:00")
        self.assertEqual(payload["end"]["dateTime"],"2026-07-15T15:00:00+02:00")
    @patch("core.calendar.requests.post")
    @patch("core.calendar.requests.put")
    def test_calendar_sync_is_per_user_and_retries_do_not_duplicate(self,put,post):
        GoogleConnection.objects.create(user=self.admin,encrypted_refresh_token=cipher().encrypt(b"refresh").decode())
        post.side_effect=[Mock(status_code=200,json=lambda:{"access_token":"access"}),Mock(status_code=201,json=lambda:{"htmlLink":"https://calendar.google.com/event"}),Mock(status_code=200,json=lambda:{"access_token":"access"})]
        put.side_effect=[Mock(status_code=404),Mock(status_code=200,json=lambda:{"htmlLink":"https://calendar.google.com/event"})]
        link=CalendarLink.objects.create(task=self.task,user=self.admin)
        self.assertTrue(sync_link(link.id));link.refresh_from_db();event_id=link.event_id
        self.assertRegex(event_id,r"^[a-v0-9]+$")
        self.assertTrue(sync_link(link.id));link.refresh_from_db();self.assertEqual(event_id,link.event_id)
        self.client.force_login(self.member)
        self.assertIsNone(self.client.get(f"/api/tasks/{self.task.id}/").json()["task"]["calendar"])
    @patch("core.calendar.requests.post")
    @patch("core.calendar.requests.put")
    def test_calendar_failure_is_visible_and_keeps_retry_id(self,put,post):
        GoogleConnection.objects.create(user=self.admin,encrypted_refresh_token=cipher().encrypt(b"refresh").decode())
        post.return_value=Mock(status_code=200,json=lambda:{"access_token":"access"})
        put.return_value=Mock(status_code=503)
        link=CalendarLink.objects.create(task=self.task,user=self.admin)
        self.assertFalse(sync_link(link.id));link.refresh_from_db()
        self.assertTrue(link.error);self.assertTrue(link.event_id);self.assertEqual(link.synced_version,0)
    @patch("core.calendar.requests.delete")
    @patch("core.calendar.requests.post")
    def test_calendar_remove_clears_id_for_readding(self,post,delete):
        GoogleConnection.objects.create(user=self.admin,encrypted_refresh_token=cipher().encrypt(b"refresh").decode())
        post.return_value=Mock(status_code=200,json=lambda:{"access_token":"access"});delete.return_value=Mock(status_code=204)
        link=CalendarLink.objects.create(task=self.task,user=self.admin,event_id="ktest",enabled=False)
        self.assertTrue(sync_link(link.id));link.refresh_from_db();self.assertEqual(link.event_id,"")
    @patch("core.worker.sync_link")
    def test_worker_deduplicates_reminders_and_skips_done(self,sync):
        self.task.due_date=timezone.localdate()+timedelta(days=1);self.task.due_time=time(0);self.task.save()
        with patch("core.worker.timezone.now",return_value=timezone.now().replace(hour=12)):
            tick();tick()
        self.assertEqual(Notification.objects.filter(dedupe_key__startswith="due:").count(),1)
        self.task.status="done";self.task.save();Notification.objects.filter(dedupe_key__startswith="due:").delete();tick()
        self.assertEqual(Notification.objects.filter(dedupe_key__startswith="due:").count(),0)
    def test_push_rejects_private_and_untrusted_endpoints(self):
        for endpoint in ["https://127.0.0.1/push","https://example.org/push","https://push.apple.com.evil.example/push"]:
            self.assertEqual(self.post("/api/push/",{"endpoint":endpoint,"keys":{}}).status_code,400)
    def test_proxy_uses_actual_last_hop_for_rate_limits(self):
        from .middleware import TrustedProxyMiddleware
        request=RequestFactory().get("/",REMOTE_ADDR="127.0.0.1",HTTP_X_FORWARDED_FOR="192.0.2.11, 198.51.100.8")
        result=TrustedProxyMiddleware(lambda r:r.META["REMOTE_ADDR"])(request)
        self.assertEqual(result,"198.51.100.8")
    def test_direct_clients_cannot_spoof_rate_limit_identity(self):
        from .middleware import TrustedProxyMiddleware
        request=RequestFactory().get("/",REMOTE_ADDR="198.51.100.8",HTTP_X_FORWARDED_FOR="192.0.2.11")
        result=TrustedProxyMiddleware(lambda r:r.META["REMOTE_ADDR"])(request)
        self.assertEqual(result,"198.51.100.8")
    def bearer(self,scope="tasks:read",resource=None):
        raw="test-opaque-token"
        AccessToken.objects.create(user=self.admin,token=raw,expires=timezone.now()+timedelta(hours=1),scope=scope,resource=[settings.APP_URL+"/mcp"] if resource is None else resource)
        return {"HTTP_AUTHORIZATION":"Bearer "+raw}
    def rpc(self,method,params=None,headers=None):
        return self.client.post("/mcp",json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or {}}),content_type="application/json",**(headers or {}))
    def test_mcp_no_session_only_access(self):
        self.assertEqual(self.rpc("tools/list").status_code,401)
    def test_mcp_read_scope_cannot_write(self):
        headers=self.bearer()
        self.assertEqual(len(self.rpc("tools/list",headers=headers).json()["result"]["tools"]),4)
        self.assertEqual(self.rpc("tools/call",{"name":"create_task","arguments":{"title":"Forbidden","project_id":str(self.project.id)}},headers).status_code,403)
    def test_mcp_rejects_wrong_resource_and_untrusted_origin(self):
        headers=self.bearer(resource=["https://other.example/mcp"])
        self.assertEqual(self.rpc("tools/list",headers=headers).status_code,401)
        self.assertEqual(self.rpc("initialize",headers={**headers,"HTTP_ORIGIN":"https://untrusted.example"}).status_code,403)
    def test_mcp_write_uses_shared_validation_and_audit(self):
        headers=self.bearer("tasks:read tasks:write")
        r=self.rpc("tools/call",{"name":"create_task","arguments":{"title":"MCP feladat","project_id":str(self.project.id)}},headers)
        self.assertFalse(r.json()["result"]["isError"])
        self.assertTrue(Task.objects.filter(title="MCP feladat").exists())
    def test_mcp_schema_rejects_unknown_arguments(self):
        r=self.rpc("tools/call",{"name":"list_tasks","arguments":{"limit":100000}},self.bearer())
        self.assertTrue(r.json()["result"]["isError"])
    def test_mcp_notification_returns_202(self):
        headers=self.bearer()
        r=self.client.post("/mcp",json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}),content_type="application/json",**headers)
        self.assertEqual(r.status_code,202)
    def test_complete_oauth_pkce_consent_code_token_refresh_flow(self):
        registration=self.post("/oauth/register/",{"client_name":"Teszt kliens","redirect_uris":["https://client.example/callback"],"grant_types":["authorization_code","refresh_token"]},client=Client())
        self.assertEqual(registration.status_code,201)
        client_id=registration.json()["client_id"]
        verifier="z"*64
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params={"client_id":client_id,"redirect_uri":"https://client.example/callback","response_type":"code","scope":"tasks:read tasks:write","state":"test-state","code_challenge":challenge,"code_challenge_method":"S256","resource":settings.APP_URL+"/mcp"}
        consent=self.client.get("/oauth/authorize/?"+urlencode(params))
        self.assertEqual(consent.status_code,200)
        authorization=self.client.post("/oauth/authorize/",{**params,"allow":"Authorize"})
        self.assertEqual(authorization.status_code,302)
        query=parse_qs(urlparse(authorization["Location"]).query)
        self.assertEqual(query["state"],["test-state"])
        metadata=self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(query.get("iss"),[metadata["issuer"]])
        code=query["code"][0]
        anon=Client()
        form=urlencode({"grant_type":"authorization_code","code":code,"redirect_uri":"https://client.example/callback","client_id":client_id,"code_verifier":verifier,"resource":settings.APP_URL+"/mcp"})
        token=anon.post("/oauth/token/",form,content_type="application/x-www-form-urlencoded")
        self.assertEqual(token.status_code,200,token.content)
        result=token.json()
        headers={"HTTP_AUTHORIZATION":"Bearer "+result["access_token"]}
        self.assertEqual(self.rpc("tools/list",headers=headers).status_code,200)
        self.assertEqual(AccessToken.objects.get().token,"")
        self.assertEqual(anon.post("/oauth/token/",form,content_type="application/x-www-form-urlencoded").status_code,400)
        refresh=anon.post("/oauth/token/",urlencode({"grant_type":"refresh_token","refresh_token":result["refresh_token"],"client_id":client_id,"resource":settings.APP_URL+"/mcp"}),content_type="application/x-www-form-urlencoded")
        self.assertEqual(refresh.status_code,200,refresh.content)
        self.assertNotEqual(refresh.json()["refresh_token"],result["refresh_token"])
    def test_oauth_rejects_wrong_resource(self):
        r=self.client.get("/oauth/authorize/?resource=https://wrong.example")
        self.assertEqual(r.status_code,400)

    def oauth_params(self):
        app=Application.objects.create(name="Issuer regression",client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://client.example/callback")
        challenge=base64.urlsafe_b64encode(hashlib.sha256(("v"*64).encode()).digest()).decode().rstrip("=")
        return {"client_id":app.client_id,"redirect_uri":app.redirect_uris,"response_type":"code",
            "scope":"tasks:read","state":"issuer-state","code_challenge":challenge,
            "code_challenge_method":"S256","resource":settings.APP_URL+"/mcp"}

    def test_oauth_metadata_advertises_canonical_issuer_and_response_support(self):
        metadata=self.client.get("/.well-known/oauth-authorization-server").json()
        resource=self.client.get("/.well-known/oauth-protected-resource/mcp").json()
        self.assertEqual(metadata["issuer"],settings.APP_URL)
        self.assertEqual(resource["authorization_servers"],[metadata["issuer"]])
        self.assertIs(metadata.get("authorization_response_iss_parameter_supported"),True)

    def test_oauth_denial_returns_same_issuer_without_code(self):
        params=self.oauth_params()
        response=self.client.post("/oauth/authorize/",params)
        self.assertEqual(response.status_code,302)
        query=parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query.get("iss"),[settings.APP_URL])
        self.assertEqual(query.get("error"),["access_denied"])
        self.assertEqual(query.get("state"),["issuer-state"])
        self.assertNotIn("code",query)
        self.assertFalse(AccessToken.objects.exists())

    def test_oauth_error_redirect_returns_same_issuer(self):
        params={**self.oauth_params(),"scope":"unknown-scope"}
        response=self.client.get("/oauth/authorize/?"+urlencode(params))
        self.assertEqual(response.status_code,302)
        query=parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query.get("iss"),[settings.APP_URL])
        self.assertEqual(query.get("error"),["invalid_scope"])
        self.assertEqual(query.get("state"),["issuer-state"])
        self.assertNotIn("code",query)

    def test_oauth_invalid_callback_still_never_redirects(self):
        params={**self.oauth_params(),"redirect_uri":"https://attacker.example/callback"}
        response=self.client.get("/oauth/authorize/?"+urlencode(params))
        self.assertEqual(response.status_code,400)
        self.assertNotIn("Location",response)
        self.assertFalse(AccessToken.objects.exists())

    @override_settings(ALLOWED_HOSTS=["testserver","alias.example"])
    def test_oauth_issuer_is_not_derived_from_request_host(self):
        params=self.oauth_params()
        response=self.client.post("/oauth/authorize/",{**params,"allow":"Authorize"},HTTP_HOST="alias.example")
        self.assertEqual(response.status_code,302)
        query=parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query.get("iss"),[settings.APP_URL])
