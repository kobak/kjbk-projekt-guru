import { useEffect, useState } from "react";
import {
  BellRing,
  CalendarDays,
  Check,
  Copy,
  ExternalLink,
  Link2,
  LoaderCircle,
  LogOut,
  Mail,
  ShieldCheck,
  UserPlus,
  X,
  KeyRound,
} from "lucide-react";
import type { Bootstrap } from "./types";
import { api } from "./api";
import { Avatar, Modal } from "./ui";
import NotificationPreferences from "./NotificationPreferences";
import ThemeSwitcher from "./ThemeSwitcher";

export default function Settings({
  data,
  onClose,
  reload,
  toast,
  onLogout,
  initialTab = "connections",
}: {
  data: Bootstrap;
  onClose: () => void;
  reload: () => Promise<void>;
  toast: (s: string) => void;
  onLogout: () => void;
  initialTab?: string;
}) {
  const [tab, setTab] = useState(initialTab),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [email, setEmail] = useState(""),
    [inviteLink, setInviteLink] = useState(""),
    [invites, setInvites] = useState<
      { id: number; email: string; expires_at: string }[]
    >([]);
  const [name, setName] = useState(data.user.name),
    [password, setPassword] = useState(""),
    [current, setCurrent] = useState(""),
    [pushOn, setPushOn] = useState(false);
  const [connections, setConnections] = useState<
    { id: number; name: string }[]
  >([]);
  const refreshInvites = () =>
    api<{ invites: typeof invites }>("invites/").then((r) =>
      setInvites(r.invites),
    );
  useEffect(() => {
    if (data.user.admin) refreshInvites().catch(() => {});
    api<{ connections: typeof connections }>("mcp/connections/")
      .then((r) => setConnections(r.connections))
      .catch(() => {});
    if ("serviceWorker" in navigator)
      navigator.serviceWorker
        .getRegistration("/")
        .then((r) => r?.pushManager.getSubscription())
        .then((s) => setPushOn(!!s))
        .catch(() => {});
  }, []);
  const run = async (fn: () => Promise<unknown>, message?: string) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await reload();
      if (message) toast(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const push = async () => {
    if (
      !("serviceWorker" in navigator) ||
      !("PushManager" in window) ||
      !("Notification" in window)
    )
      throw new Error(
        "Ez a böngésző most nem támogatja a push értesítéseket. iPhone-on add a kjbk projekt gurut a Főképernyőhöz, és onnan nyisd meg.",
      );
    if (Notification.permission === "denied")
      throw new Error(
        "Az értesítések le vannak tiltva. Engedélyezd őket a böngésző vagy a telefon beállításaiban.",
      );
    if (!pushOn) {
      const permission = await Notification.requestPermission();
      if (permission !== "granted")
        throw new Error(
          "Az értesítéseket nem engedélyezted. Az alkalmazáson belüli értesítések ettől még működnek.",
        );
    }
    const registration = await navigator.serviceWorker.register("/sw.js", {
      scope: "/",
    });
    await navigator.serviceWorker.ready;
    const previous = await registration.pushManager.getSubscription();
    if (previous && pushOn) {
      await api("push/", "DELETE", previous.toJSON());
      await previous.unsubscribe();
      setPushOn(false);
      return;
    }
    const raw = atob(
      data.integrations.vapid_public_key.replace(/-/g, "+").replace(/_/g, "/"),
    );
    const key = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    const sub =
      previous ||
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key,
      }));
    await api("push/", "POST", sub.toJSON());
    setPushOn(true);
  };
  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast("Vágólapra másolva");
    } catch {
      setError("A másolás nem sikerült. Jelöld ki és másold a címet.");
    }
  };
  const googleState = new URLSearchParams(location.search).get("google");
  return (
    <Modal title="Beállítások" onClose={onClose} wide>
      <div className="task-tabs">
        <button
          className={tab === "connections" ? "active" : ""}
          onClick={() => setTab("connections")}
        >
          Kapcsolatok
        </button>
        <button
          className={tab === "notifications" ? "active" : ""}
          onClick={() => setTab("notifications")}
        >
          Értesítések
        </button>
        <button
          className={tab === "team" ? "active" : ""}
          onClick={() => setTab("team")}
        >
          Csapat
        </button>
        <button
          className={tab === "profile" ? "active" : ""}
          onClick={() => setTab("profile")}
        >
          Saját fiók
        </button>
      </div>
      <div className="settings-content">
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        {tab === "notifications" && (
          <NotificationPreferences
            pushOn={pushOn}
            onManagePush={() => setTab("connections")}
            onSaved={() => toast("Értesítési beállítások elmentve")}
          />
        )}
        {tab === "connections" && (
          <>
            <section className="settings-section">
              <div className="section-icon google-icon">
                <CalendarDays size={23} />
              </div>
              <div className="settings-heading">
                <h3>Google Naptár</h3>
                <span
                  className={
                    "connection-status " +
                    (data.integrations.google_connected ? "connected" : "")
                  }
                >
                  {data.integrations.google_connected
                    ? "Csatlakoztatva"
                    : "Nincs csatlakoztatva"}
                </span>
              </div>
              <p>
                A feladatok határidejét a saját naptáradba teheted. A későbbi
                módosítások automatikusan követik a feladatot.
              </p>
              {googleState && googleState !== "connected" && (
                <div className="error-banner">
                  {googleState === "cancelled"
                    ? "A csatlakozást megszakítottad."
                    : "A Google-csatlakozás nem sikerült. Ellenőrizd a szerver OAuth-beállításait, majd próbáld újra."}
                </div>
              )}
              {!data.integrations.google_configured ? (
                <div className="setup-note">
                  <ShieldCheck size={18} />
                  <span>
                    A szerveren még be kell állítani a Google OAuth-azonosítót.
                    Ezután itt mindenki a saját Google-fiókjával csatlakozhat.
                  </span>
                </div>
              ) : data.integrations.google_connected ? (
                <div className="button-row">
                  <a
                    className="btn secondary compact"
                    href="/api/google/connect/"
                  >
                    Újracsatlakozás
                    <ExternalLink size={14} />
                  </a>
                  <button
                    className="text-btn"
                    disabled={busy}
                    onClick={() => {
                      if (confirm("Leválasztod a Google Naptáradat?"))
                        run(
                          () => api("google/disconnect/", "POST"),
                          "Naptár leválasztva",
                        );
                    }}
                  >
                    Leválasztás
                  </button>
                </div>
              ) : (
                <a href="/api/google/connect/" className="btn primary">
                  <Link2 size={16} />
                  Saját naptár csatlakoztatása
                </a>
              )}
            </section>
            <section className="settings-section">
              <div className="section-icon">
                <BellRing size={23} />
              </div>
              <div className="settings-heading">
                <h3>Push értesítések</h3>
                <span
                  className={"connection-status " + (pushOn ? "connected" : "")}
                >
                  {pushOn ? "Bekapcsolva ezen az eszközön" : "Kikapcsolva"}
                </span>
              </div>
              <p>
                Új feladatok, hozzászólások és közelgő határidők, akkor is, ha
                az alkalmazás nincs megnyitva. Az alkalmazáson belüli
                értesítések mindig elérhetők.
              </p>
              <button
                className="btn secondary"
                disabled={busy || !data.integrations.push_configured}
                onClick={() =>
                  run(
                    push,
                    pushOn
                      ? "Push kikapcsolva"
                      : "Push értesítések bekapcsolva",
                  )
                }
              >
                <BellRing size={16} />
                {pushOn
                  ? "Kikapcsolás ezen az eszközön"
                  : "Értesítések engedélyezése"}
              </button>
              <p className="form-hint">
                iPhone-on: Megosztás → Főképernyőhöz adás, majd az alkalmazásból
                engedélyezd az értesítést. Internetkapcsolat és HTTPS szükséges.
              </p>
            </section>
            <section className="settings-section">
              <div className="section-icon">
                <Link2 size={23} />
              </div>
              <h3>ChatGPT és Claude</h3>
              <p>
                A közös projekteket és feladatokat az AI-beszélgetéseidből is
                kezelheted. A kapcsolat a saját fiókoddal, külön jóváhagyással
                működik.
              </p>
              <div className="copy-field">
                <code>{data.integrations.mcp_url}</code>
                <button
                  className="icon-btn"
                  aria-label="MCP-cím másolása"
                  onClick={() => copy(data.integrations.mcp_url)}
                >
                  <Copy size={16} />
                </button>
              </div>
              <p className="form-hint">
                Add hozzá ezt az MCP-címet a ChatGPT vagy Claude egyéni
                kapcsolataihoz. A megnyíló kjbk projekt guru oldalon jelentkezz
                be és engedélyezd a hozzáférést. Nyilvánosan elérhető HTTPS-cím
                kell.
              </p>
              {connections.map((c) => (
                <div key={c.id} className="member-row">
                  <KeyRound size={17} />
                  <strong>{c.name}</strong>
                  <button
                    className="text-btn danger"
                    onClick={() =>
                      run(async () => {
                        await api("mcp/connections/", "DELETE", { id: c.id });
                        setConnections((v) => v.filter((x) => x.id !== c.id));
                      }, "MCP-hozzáférés visszavonva")
                    }
                  >
                    Visszavonás
                  </button>
                </div>
              ))}
            </section>
          </>
        )}
        {tab === "team" && (
          <>
            <div className="settings-intro">
              <h3>Egy csapat. Közös haladás.</h3>
              <p>
                Minden tag hozzáfér az összes közös projekthez.{" "}
                {data.members.length}/5 hely foglalt.
              </p>
            </div>
            {data.members.map((u) => (
              <div key={u.id} className="member-row">
                <Avatar user={u} />
                <div>
                  <strong>
                    {u.name}
                    {u.id === data.user.id ? " (te)" : ""}
                  </strong>
                  <span>{u.email}</span>
                </div>
                <span className="role-tag">{u.admin ? "Admin" : "Tag"}</span>
                {data.user.admin && !u.admin && u.id !== data.user.id && (
                  <button
                    className="icon-btn"
                    aria-label={`${u.name} hozzáférésének megszüntetése`}
                    onClick={() => {
                      if (confirm(`Megszünteted ${u.name} hozzáférését?`))
                        run(
                          () => api(`members/${u.id}/deactivate/`, "POST"),
                          "Hozzáférés megszüntetve",
                        );
                    }}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            ))}
            {data.user.admin && (
              <section className="invite-section">
                <h3>
                  <UserPlus size={18} />
                  Csapattag meghívása
                </h3>
                <p>
                  A meghívó 7 napig érvényes. A linket te küldheted el a
                  csapattársnak.
                </p>
                <form
                  className="invite-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () => {
                      const r = await api<{ url: string }>("invites/", "POST", {
                        email,
                      });
                      setInviteLink(r.url);
                      setEmail("");
                      await refreshInvites();
                    });
                  }}
                >
                  <label className="input-with-icon">
                    <Mail size={16} />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="csapattars@email.hu"
                      required
                    />
                  </label>
                  <button
                    className="btn primary"
                    disabled={busy || data.members.length >= 5}
                  >
                    Meghívó létrehozása
                  </button>
                </form>
                {inviteLink && (
                  <div className="invite-result">
                    <p>
                      <Check size={16} />A meghívó elkészült. Másold ki és küldd
                      el!
                    </p>
                    <div className="copy-field">
                      <input
                        readOnly
                        value={inviteLink}
                        aria-label="Meghívó linkje"
                        onFocus={(e) => e.target.select()}
                      />
                      <button
                        className="icon-btn"
                        aria-label="Meghívó másolása"
                        onClick={() => copy(inviteLink)}
                      >
                        <Copy size={16} />
                      </button>
                    </div>
                  </div>
                )}
                {invites.map((i) => (
                  <div className="pending-invite" key={i.id}>
                    <span>
                      {i.email}
                      <small>
                        Meghívás elküldésre vár ·{" "}
                        {new Date(i.expires_at).toLocaleDateString("hu-HU")}-ig
                      </small>
                    </span>
                    <button
                      className="text-btn danger"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api("invites/", "DELETE", { id: i.id });
                          await refreshInvites();
                        }, "Meghívó visszavonva")
                      }
                    >
                      Visszavonás
                    </button>
                  </div>
                ))}
              </section>
            )}
          </>
        )}
        {tab === "profile" && (
          <>
            <ThemeSwitcher settings />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  await api("profile/", "PATCH", {
                    name,
                    ...(password
                      ? { password, current_password: current }
                      : {}),
                  });
                  setPassword("");
                  setCurrent("");
                }, "Fiók frissítve");
              }}
            >
              <div className="profile-avatar">
                <Avatar user={data.user} size="large" />
                <div>
                  <h3>{data.user.name}</h3>
                  <p>{data.user.email}</p>
                </div>
              </div>
              <label>
                Megjelenő név
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={100}
                />
              </label>
              <h3 className="password-heading">Jelszó módosítása</h3>
              <label>
                Jelenlegi jelszó
                <input
                  type="password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <label>
                Új jelszó <span className="muted">· legalább 10 karakter</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={10}
                />
              </label>
              <button className="btn primary" disabled={busy}>
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Check size={16} />
                )}
                Mentés
              </button>
            </form>
            <div className="signout-section">
              <button className="text-btn danger" onClick={onLogout}>
                <LogOut size={16} />
                Kijelentkezés
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
