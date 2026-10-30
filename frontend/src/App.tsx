import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUp,
  Bell,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  CircleCheck,
  Clock3,
  FolderKanban,
  LayoutDashboard,
  LayoutGrid,
  List,
  LoaderCircle,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Target,
  Users,
  X,
  CalendarCheck,
  AlertCircle,
  RefreshCw,
  Archive,
  Pencil,
} from "lucide-react";
import { api, ApiError, today, dayLabel, relative, isOverdue } from "./api";
import type {
  Appearance,
  Bootstrap,
  ListOrder,
  ListSort,
  Member,
  Project,
  Status,
  Task,
} from "./types";
import { Avatar, Modal, StatusMark, statuses, priorities } from "./ui";
import TaskPanel from "./TaskPanel";
import TaskList from "./TaskList";
import { sortListTasks } from "./listSorting";
import Settings from "./Settings";
import Brand, { brandProjectColor, projectDisplayColor } from "./Brand";
import ThemeSwitcher from "./ThemeSwitcher";
import {
  chooseAppearance,
  resetAppearance,
  syncAppearance,
  useAppearance,
} from "./theme";

type Page = "overview" | "projects" | "mine" | "calendar";
type View = "board" | "list" | "calendar";

function Login({ onLogin }: { onLogin: () => void }) {
  const token = new URLSearchParams(location.search).get("invite");
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [validInvite, setValidInvite] = useState(!token);
  useEffect(() => {
    if (token)
      api<{ email: string }>(`invites/${token}/`)
        .then((r) => {
          setEmail(r.email);
          setValidInvite(true);
        })
        .catch(() =>
          setError(
            "A meghívó lejárt, már felhasználták vagy visszavonták. Kérj újat az adminisztrátortól.",
          ),
        );
  }, [token]);
  return (
    <div className="auth-page">
      <div className="auth-theme-switcher">
        <ThemeSwitcher />
      </div>
      <div className="auth-intro">
        <a className="brand" href="/">
          <Brand full />
        </a>
        <div className="auth-art">
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div className="art-card art-card-one">
            <span className="art-dot" />
            Az ötletből terv.
          </div>
          <div className="art-card art-card-two">
            <span className="art-check">
              <Check size={18} />
            </span>
            A tervből kész.
          </div>
          <div className="art-cross">+</div>
        </div>
        <h1>
          Van egy közös
          <br />
          jó helyünk.
        </h1>
        <p>
          Projektek, feladatok és a következő lépés.
          <br />
          Átláthatóan, együtt.
        </p>
        <span className="auth-caption">Kis csapat. Közös lendület.</span>
      </div>
      <div className="auth-form-wrap">
        <div className="auth-form">
          <span className="eyebrow">A MI MUNKATERÜNK</span>
          <h2>{token ? "Jó, hogy csatlakozol." : "Szia, jó újra itt."}</h2>
          <p>
            {token
              ? "Hozd létre a fiókodat a közös munkatérhez."
              : "Lépj be, és folytassuk, ahol abbahagytuk."}
          </p>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api(
                  token ? `invites/${token}/` : "login/",
                  "POST",
                  token ? { name, password } : { email, password },
                );
                if (token) history.replaceState(null, "", "/");
                onLogin();
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {token && (
              <label>
                Neved
                <input
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoFocus
                  maxLength={100}
                />
              </label>
            )}
            <label>
              E-mail-cím
              <input
                type="email"
                autoComplete="username"
                placeholder="nev@email.hu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                readOnly={!!token}
                autoFocus={!token}
              />
            </label>
            <label>
              Jelszó
              <input
                type="password"
                autoComplete={token ? "new-password" : "current-password"}
                placeholder={token ? "Legalább 10 karakter" : "A jelszavad"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={token ? 10 : undefined}
              />
            </label>
            <button
              className="btn primary full"
              disabled={busy || !validInvite}
            >
              {busy ? <LoaderCircle size={17} className="spin" /> : null}
              {token ? "Csatlakozás a csapathoz" : "Belépés a munkatérbe"}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="login-note">
            {token
              ? "A meghívóval az összes közös projekthez hozzáférsz."
              : "Meghívásos munkatér. Új fiókhoz kérj meghívót az adminisztrátortól."}
          </p>
        </div>
        <span className="auth-footer">Kevesebb keresgélés. Több haladás.</span>
      </div>
    </div>
  );
}

export default function App() {
  const appearance = useAppearance();
  const [session, setSession] = useState<Member | null | undefined>(undefined),
    [data, setData] = useState<Bootstrap | null>(null),
    [fatal, setFatal] = useState("");
  const [page, setPage] = useState<Page>("overview"),
    [projectId, setProjectId] = useState<string | null>(null),
    [view, setView] = useState<View | null>(null),
    [sidebar, setSidebar] = useState(false);
  const [query, setQuery] = useState(""),
    [memberFilter, setMemberFilter] = useState(""),
    [priorityFilter, setPriorityFilter] = useState(""),
    [showDone, setShowDone] = useState(true),
    [statusFilter, setStatusFilter] = useState(""),
    [archivedOpen, setArchivedOpen] = useState(false),
    [filtersOpen, setFiltersOpen] = useState(false);
  const [taskEditor, setTaskEditor] = useState<{
      id: string | null;
      status?: Status;
    } | null>(null),
    [projectEditor, setProjectEditor] = useState<Project | "new" | null>(null),
    [settingsOpen, setSettingsOpen] = useState(
      new URLSearchParams(location.search).has("settings"),
    );
  const [settingsInitialTab, setSettingsInitialTab] = useState(
    new URLSearchParams(location.search).get("settings") === "notifications"
      ? "notifications"
      : "connections",
  );
  const [noticesOpen, setNoticesOpen] = useState(false),
    [toast, setToast] = useState(""),
    [refreshing, setRefreshing] = useState(false),
    [focusOwn, setFocusOwn] = useState(true);
  const searchRef = useRef<HTMLInputElement>(null),
    toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const showToast = useCallback((s: string) => {
    setToast(s);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4000);
  }, []);
  const reload = useCallback(async () => {
    try {
      const next = await api<Bootstrap>("bootstrap/");
      syncAppearance(next.user.id, next.appearance);
      next.projects = next.projects.map((project) => ({
        ...project,
        color: brandProjectColor(project.color),
      }));
      setData((previous) =>
        previous?.user.id === next.user.id &&
        previous.list_order.version > next.list_order.version
          ? { ...next, list_order: previous.list_order }
          : next,
      );
      setSession(next.user);
      setFatal("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        resetAppearance();
        setSession(null);
        setData(null);
      } else throw e;
    }
  }, []);
  const loadSession = useCallback(async () => {
    setFatal("");
    try {
      const r = await api<{ user: Member | null; appearance: Appearance }>(
        "session/",
      );
      syncAppearance(r.user?.id || null, r.appearance);
      setSession(r.user);
      if (r.user) await reload();
    } catch (e) {
      setFatal((e as Error).message);
    }
  }, [reload]);
  useEffect(() => {
    loadSession();
  }, [loadSession]);
  useEffect(() => setView(null), [appearance.default_view]);
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => {
      if (!document.hidden) reload().catch(() => {});
    }, 30000);
    const visible = () => {
      if (!document.hidden) reload().catch(() => {});
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [!!session, reload]);
  useEffect(() => {
    if (!data) return;
    const t = new URLSearchParams(location.search).get("task");
    if (t) {
      setTaskEditor({ id: t });
      history.replaceState(null, "", "/");
    }
  }, [!!data]);
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      const editing = (e.target as HTMLElement).closest(
        "input,textarea,select,[contenteditable]",
      );
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (
        !editing &&
        !taskEditor &&
        !settingsOpen &&
        !projectEditor &&
        e.key.toLowerCase() === "n" &&
        session
      ) {
        setTaskEditor({ id: null });
      }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [session, taskEditor, settingsOpen, projectEditor]);
  const go = (next: Page, id: string | null = null) => {
    setPage(next);
    setProjectId(id);
    setQuery("");
    setSidebar(false);
    setMemberFilter("");
    setPriorityFilter("");
    setStatusFilter("");
    setShowDone(true);
    setView(null);
    window.scrollTo({ top: 0 });
  };
  const updateStatus = async (t: Task, status: Status) => {
    try {
      await api(`tasks/${t.id}/`, "PATCH", { status, version: t.version });
      await reload();
      showToast(
        status === "done"
          ? "Még egy lépéssel előrébb. Kész!"
          : "Állapot frissítve",
      );
    } catch (e) {
      showToast((e as Error).message);
      await reload();
    }
  };
  const project = data?.projects.find((p) => p.id === projectId);
  const currentView =
    page === "calendar" ? "calendar" : view || appearance.default_view;
  const visibleCompleted =
    currentView === "list" ? appearance.show_completed : showDone;
  const changeCompleted = (value: boolean) => {
    if (!value && statusFilter === "done") setStatusFilter("");
    if (currentView === "list") chooseAppearance({ show_completed: value });
    else setShowDone(value);
  };
  const activeTasks =
    data?.tasks.filter(
      (t) => !data.projects.find((p) => p.id === t.project_id)?.archived,
    ) || [];
  const filtered = useMemo(
    () =>
      data?.tasks.filter((t) => {
        if (
          projectId
            ? t.project_id !== projectId
            : data.projects.find((p) => p.id === t.project_id)?.archived
        )
          return false;
        if (page === "mine" && t.assignee_id !== data.user.id) return false;
        if (
          memberFilter &&
          (memberFilter === "none"
            ? t.assignee_id !== null
            : t.assignee_id !== Number(memberFilter))
        )
          return false;
        if (priorityFilter && t.priority !== priorityFilter) return false;
        if (!visibleCompleted && statusFilter !== "done" && t.status === "done")
          return false;
        if (statusFilter && t.status !== statusFilter) return false;
        return (
          !query ||
          `${t.title} ${t.description} ${t.labels.join(" ")}`
            .toLocaleLowerCase("hu")
            .includes(query.toLocaleLowerCase("hu"))
        );
      }) || [],
    [
      data,
      projectId,
      page,
      memberFilter,
      priorityFilter,
      query,
      visibleCompleted,
      statusFilter,
    ],
  );
  const listTasks = useMemo(
    () =>
      sortListTasks(
        filtered,
        appearance.list_sort,
        data?.list_order.task_ids || [],
      ),
    [filtered, appearance.list_sort, data?.list_order],
  );
  if (fatal && !data)
    return (
      <div className="loading-screen">
        <AlertCircle size={30} />
        <h2>Nem sikerült kapcsolódni.</h2>
        <p>{fatal}</p>
        <button className="btn primary" onClick={loadSession}>
          <RefreshCw size={16} />
          Újrapróbálás
        </button>
      </div>
    );
  if (session === undefined || (session && !data))
    return (
      <div className="loading-screen">
        <span className="brand">
          <Brand />
        </span>
        <LoaderCircle className="spin" />
        <p>Minden a helyére kerül…</p>
      </div>
    );
  if (!session || !data) return <Login onLogin={() => loadSession()} />;
  const open = activeTasks.filter((t) => t.status !== "done"),
    dueToday = open.filter((t) => t.due_date === today()),
    overdue = open.filter(isOverdue),
    done = activeTasks.filter((t) => t.status === "done");
  const focusTasks = [...open]
    .filter(
      (t) =>
        (!focusOwn || t.assignee_id === data.user.id) &&
        (!t.due_date || t.due_date <= today()),
    )
    .sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999"))
    .slice(0, 5);
  const isOverview = page === "overview" && !query;
  const createTask = (status?: Status) => {
    if (!data.projects.some((p) => !p.archived)) {
      setProjectEditor("new");
      showToast("Először hozzunk létre egy projektet.");
    } else setTaskEditor({ id: null, status });
  };
  const projectProgress = (p: Project) => {
    const ts = data.tasks.filter((t) => t.project_id === p.id);
    return ts.length
      ? Math.round(
          (100 * ts.filter((t) => t.status === "done").length) / ts.length,
        )
      : 0;
  };
  return (
    <div className="app-shell">
      {sidebar && (
        <div className="sidebar-scrim" onClick={() => setSidebar(false)} />
      )}
      <aside className={"sidebar " + (sidebar ? "open" : "")}>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            go("overview");
          }}
        >
          <Brand />
        </a>
        <div className="workspace-label">
          <span className="workspace-symbol">
            <Users size={15} />
          </span>
          <div>
            <strong>{data.workspace}</strong>
            <span>{data.members.length} csapattag</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav className="main-nav">
          <button
            className={page === "overview" ? "active" : ""}
            onClick={() => go("overview")}
          >
            <LayoutDashboard size={18} />
            Áttekintés
          </button>
          <button
            className={page === "mine" ? "active" : ""}
            onClick={() => go("mine")}
          >
            <CircleCheck size={18} />
            Saját feladatok
            <span className="nav-count">
              {open.filter((t) => t.assignee_id === data.user.id).length}
            </span>
          </button>
          <button
            className={page === "calendar" ? "active" : ""}
            onClick={() => go("calendar")}
          >
            <CalendarDays size={18} />
            Naptár
          </button>
        </nav>
        <div className="nav-section-title">
          <button onClick={() => go("projects")}>
            PROJEKTEK{" "}
            <span>{data.projects.filter((p) => !p.archived).length}</span>
          </button>
          <button
            className="icon-btn small"
            aria-label="Új projekt"
            onClick={() => setProjectEditor("new")}
          >
            <Plus size={16} />
          </button>
        </div>
        <nav className="project-nav">
          <button
            className={page === "projects" && !projectId ? "active" : ""}
            onClick={() => go("projects")}
          >
            <FolderKanban size={17} />
            Összes projekt
          </button>
          {data.projects
            .filter((p) => !p.archived)
            .map((p) => (
              <button
                key={p.id}
                className={projectId === p.id ? "active" : ""}
                onClick={() => go("projects", p.id)}
              >
                <span
                  className="project-dot"
                  style={{ background: projectDisplayColor(p.color) }}
                />
                {p.name}
                <span className="project-nav-count">
                  {
                    data.tasks.filter(
                      (t) => t.project_id === p.id && t.status !== "done",
                    ).length
                  }
                </span>
              </button>
            ))}
          {data.projects.some((p) => p.archived) && (
            <>
              <button
                className="archived-toggle"
                onClick={() => setArchivedOpen(!archivedOpen)}
              >
                <Archive size={14} />
                Archivált projektek
                <ChevronDown size={12} />
              </button>
              {archivedOpen &&
                data.projects
                  .filter((p) => p.archived)
                  .map((p) => (
                    <button key={p.id} onClick={() => go("projects", p.id)}>
                      <span
                        className="project-dot"
                        style={{ background: projectDisplayColor(p.color) }}
                      />
                      {p.name}
                    </button>
                  ))}
            </>
          )}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <span className="note-sprout">✳</span>
          <strong>Együtt haladunk.</strong>
          <p>A következő lépés már itt vár.</p>
        </div>
        <button
          className="sidebar-settings"
          onClick={() => setSettingsOpen(true)}
        >
          <Settings2 size={18} />
          Beállítások
        </button>
        <button
          className="profile-button"
          onClick={() => setSettingsOpen(true)}
        >
          <Avatar user={data.user} />
          <span>
            <strong>{data.user.name}</strong>
            <small>
              {data.user.admin ? "Munkatér adminisztrátora" : "Csapattag"}
            </small>
          </span>
          <MoreHorizontal size={17} />
        </button>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-btn mobile-menu"
            onClick={() => setSidebar(true)}
            aria-label="Menü megnyitása"
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            <span>Munkatér</span>
            <ChevronRight size={13} />
            <strong>
              {project?.name ||
                (page === "overview"
                  ? "Áttekintés"
                  : page === "mine"
                    ? "Saját feladatok"
                    : page === "calendar"
                      ? "Naptár"
                      : "Projektek")}
            </strong>
          </div>
          <div className="topbar-right">
            <label className="search-box">
              <Search size={16} />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Feladat keresése…"
                aria-label="Feladat keresése"
              />
              <kbd>⌘ K</kbd>
              {query && (
                <button
                  className="icon-btn small"
                  onClick={() => setQuery("")}
                  aria-label="Keresés törlése"
                >
                  <X size={13} />
                </button>
              )}
            </label>
            <div className="topbar-divider" />
            <div className="team-avatars">
              {data.members.slice(0, 4).map((u) => (
                <Avatar key={u.id} user={u} size="small" />
              ))}
            </div>
            <button
              className={"icon-btn bell-btn " + (noticesOpen ? "selected" : "")}
              aria-label={`Értesítések, ${data.unread} olvasatlan`}
              onClick={() => setNoticesOpen(!noticesOpen)}
            >
              <Bell size={19} />
              {data.unread > 0 && <span className="notification-dot" />}
            </button>
            <ThemeSwitcher
              onSettings={() => {
                setSettingsInitialTab("profile");
                setSettingsOpen(true);
              }}
            />
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              {isOverview ? (
                <>
                  <span className="eyebrow">
                    {new Intl.DateTimeFormat("hu-HU", {
                      timeZone: "Europe/Budapest",
                      weekday: "long",
                      month: "long",
                      day: "numeric",
                    })
                      .format(new Date())
                      .toLocaleUpperCase("hu")}
                  </span>
                  <h1>
                    Szia, {data.user.name.split(" ").at(-1)}
                    <span className="greeting-dot">.</span>
                  </h1>
                  <p>Nézzük, min dolgozunk ma közösen.</p>
                </>
              ) : (
                <>
                  <div className="eyebrow">
                    {query
                      ? "KERESÉSI TALÁLATOK"
                      : project
                        ? "KÖZÖS PROJEKT"
                        : page === "mine"
                          ? "A TE KÖVETKEZŐ LÉPÉSEID"
                          : page === "calendar"
                            ? "HATÁRIDŐK EGY HELYEN"
                            : "A MI MUNKÁNK"}
                  </div>
                  <h1>
                    {query
                      ? `„${query}”`
                      : project?.name ||
                        (page === "mine"
                          ? "Saját feladatok"
                          : page === "calendar"
                            ? "Csapatnaptár"
                            : "Összes feladat")}
                    {project && (
                      <span
                        className="project-title-dot"
                        style={{
                          background: projectDisplayColor(project.color),
                        }}
                      />
                    )}
                  </h1>
                  <p>
                    {query
                      ? `${filtered.length} találat a munkatér feladatai között.`
                      : project?.description ||
                        (page === "mine"
                          ? "A hozzád rendelt feladatok, egy helyen."
                          : page === "calendar"
                            ? "Lásd előre a következő napokat."
                            : "Minden projekt. Minden következő lépés.")}
                  </p>
                </>
              )}
            </div>
            <div className="heading-actions">
              {project && (
                <button
                  className="btn secondary compact project-edit"
                  onClick={() => setProjectEditor(project)}
                >
                  <Pencil size={15} />
                  Projekt
                </button>
              )}
              <button
                className="btn primary"
                onClick={() => createTask()}
                disabled={project?.archived}
              >
                <Plus size={17} />
                Új feladat<span className="button-shortcut">N</span>
              </button>
            </div>
          </div>
          {isOverview ? (
            <>
              <div className="stats-grid">
                <button className="stat-card" onClick={() => go("projects")}>
                  <span className="stat-label">
                    Aktív projektek
                    <FolderKanban size={16} />
                  </span>
                  <div>
                    <strong>
                      {data.projects.filter((p) => !p.archived).length}
                    </strong>
                    <span className="stat-foot">közös cél</span>
                  </div>
                  <div className="stat-mini-blocks">
                    {data.projects
                      .filter((p) => !p.archived)
                      .slice(0, 8)
                      .map((p) => (
                        <i
                          key={p.id}
                          style={{ background: projectDisplayColor(p.color) }}
                        />
                      ))}
                  </div>
                </button>
                <button
                  className="stat-card"
                  onClick={() => {
                    go("projects");
                    setShowDone(false);
                    setFiltersOpen(true);
                  }}
                >
                  <span className="stat-label">
                    Nyitott feladatok
                    <Circle size={16} />
                  </span>
                  <div>
                    <strong>{open.length}</strong>
                    <span className="stat-foot">amin dolgozunk</span>
                  </div>
                  <div className="stat-progress">
                    <span
                      style={{
                        width: `${activeTasks.length ? (done.length / activeTasks.length) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </button>
                <button className="stat-card" onClick={() => go("calendar")}>
                  <span className="stat-label">
                    Mai határidők
                    <Clock3 size={16} />
                  </span>
                  <div>
                    <strong>{dueToday.length}</strong>
                    <span className="stat-foot">
                      {overdue.length
                        ? `${overdue.length} korábbi határidő`
                        : "minden időben"}
                    </span>
                  </div>
                  <span
                    className={"stat-badge " + (overdue.length ? "warm" : "")}
                  >
                    <span />
                    {overdue.length ? "Van még pótolnivaló" : "Nézzünk előre"}
                  </span>
                </button>
                <button
                  className="stat-card green"
                  onClick={() => {
                    go("projects");
                    setView("list");
                    setStatusFilter("done");
                    setFiltersOpen(true);
                  }}
                >
                  <span className="stat-label">
                    Elkészült feladatok
                    <CheckCheck size={17} />
                  </span>
                  <div>
                    <strong>{done.length}</strong>
                    <span className="stat-foot">közös siker</span>
                  </div>
                  <span className="stat-encouragement">
                    <Sparkles size={14} />
                    Minden lépés számít.
                  </span>
                </button>
              </div>
              <section className="overview-projects">
                <div className="section-heading">
                  <h2>
                    Projektjeink{" "}
                    <span>
                      {data.projects.filter((p) => !p.archived).length}
                    </span>
                  </h2>
                  <button
                    className="text-btn"
                    onClick={() => setProjectEditor("new")}
                  >
                    <Plus size={15} />
                    Új projekt
                  </button>
                </div>
                <div className="project-card-grid">
                  {data.projects
                    .filter((p) => !p.archived)
                    .map((p) => {
                      const ts = data.tasks.filter(
                          (t) => t.project_id === p.id,
                        ),
                        people = data.members.filter((u) =>
                          ts.some((t) => t.assignee_id === u.id),
                        );
                      return (
                        <button
                          key={p.id}
                          className="project-card"
                          onClick={() => go("projects", p.id)}
                        >
                          <div className="project-card-top">
                            <span
                              className="project-icon"
                              style={{
                                background: p.color + "18",
                                color: projectDisplayColor(p.color),
                              }}
                            >
                              <FolderKanban size={21} />
                            </span>
                            <ArrowRight size={17} />
                          </div>
                          <h3>{p.name}</h3>
                          <p>{p.description || "A következő közös célunk."}</p>
                          <div className="project-progress-label">
                            <span>
                              {ts.filter((t) => t.status === "done").length} /{" "}
                              {ts.length} feladat kész
                            </span>
                            <strong>{projectProgress(p)}%</strong>
                          </div>
                          <div className="project-progress">
                            <span
                              style={{
                                width: projectProgress(p) + "%",
                                background: projectDisplayColor(p.color),
                              }}
                            />
                          </div>
                          <div className="project-card-bottom">
                            <div className="team-avatars">
                              {people.map((u) => (
                                <Avatar key={u.id} user={u} size="tiny" />
                              ))}
                            </div>
                            <span>
                              {ts.filter((t) => t.status !== "done").length}{" "}
                              nyitott
                              <ChevronRight size={13} />
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  <button
                    className="new-project-card"
                    onClick={() => setProjectEditor("new")}
                  >
                    <span>
                      <Plus size={23} />
                    </span>
                    <strong>Van egy új közös cél?</strong>
                    <small>Hozzunk létre egy projektet.</small>
                  </button>
                </div>
              </section>
              <div className="overview-bottom">
                <section className="focus-section">
                  <div className="section-heading">
                    <h2>
                      Mai fókusz{" "}
                      <span className="small-icon">
                        <Target size={16} />
                      </span>
                    </h2>
                    <div className="segmented compact">
                      <button
                        className={focusOwn ? "active" : ""}
                        onClick={() => setFocusOwn(true)}
                      >
                        Saját
                      </button>
                      <button
                        className={!focusOwn ? "active" : ""}
                        onClick={() => setFocusOwn(false)}
                      >
                        Csapat
                      </button>
                    </div>
                  </div>
                  <div className="focus-card">
                    {focusTasks.length ? (
                      focusTasks.map((t) => (
                        <div className="focus-task" key={t.id}>
                          <StatusMark
                            value={t.status}
                            onClick={() => updateStatus(t, "done")}
                          />
                          <button
                            className="focus-title"
                            onClick={() => setTaskEditor({ id: t.id })}
                          >
                            <strong>{t.title}</strong>
                            <span>
                              <i
                                style={{
                                  background: projectDisplayColor(
                                    data.projects.find(
                                      (p) => p.id === t.project_id,
                                    )?.color,
                                  ),
                                }}
                              />
                              {
                                data.projects.find((p) => p.id === t.project_id)
                                  ?.name
                              }
                            </span>
                          </button>
                          <span
                            className={
                              "due-pill " + (isOverdue(t) ? "overdue" : "")
                            }
                          >
                            {dayLabel(t.due_date)}
                            {t.due_time && " · " + t.due_time}
                          </span>
                          <Avatar
                            user={data.members.find(
                              (u) => u.id === t.assignee_id,
                            )}
                            size="small"
                          />
                        </div>
                      ))
                    ) : (
                      <div className="empty-small">
                        <CircleCheck size={30} />
                        <h3>Ma minden a helyén.</h3>
                        <p>Nincs erre a napra váró feladatod.</p>
                      </div>
                    )}
                    <button
                      className="focus-all"
                      onClick={() => go(focusOwn ? "mine" : "projects")}
                    >
                      Minden {focusOwn ? "saját " : ""}feladat
                      <ArrowRight size={15} />
                    </button>
                  </div>
                </section>
                <section className="activity-section">
                  <div className="section-heading">
                    <h2>Ez történt nálunk</h2>
                    <span className="live-dot">Friss</span>
                  </div>
                  <div className="activity-card">
                    {data.activity.length ? (
                      data.activity.slice(0, 5).map((a) => (
                        <button
                          className="activity-item"
                          key={a.id}
                          onClick={() =>
                            a.task_id && setTaskEditor({ id: a.task_id })
                          }
                        >
                          <Avatar user={a.user} size="small" />
                          <div>
                            <p>
                              <strong>{a.user.name}</strong> {a.text}
                            </p>
                            <span>{a.task_title}</span>
                            <time>{relative(a.created_at)}</time>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="empty-small">
                        <Users size={28} />
                        <p>Itt látod majd a csapat legutóbbi lépéseit.</p>
                      </div>
                    )}
                  </div>
                </section>
              </div>
            </>
          ) : (
            <>
              {project && (
                <div className="project-summary">
                  <div className="team-avatars">
                    {data.members
                      .filter((u) =>
                        data.tasks.some(
                          (t) =>
                            t.project_id === project.id &&
                            t.assignee_id === u.id,
                        ),
                      )
                      .map((u) => (
                        <Avatar key={u.id} user={u} size="small" />
                      ))}
                  </div>
                  <span>{filtered.length} feladat</span>
                  <div className="project-progress">
                    <span
                      style={{
                        width: projectProgress(project) + "%",
                        background: projectDisplayColor(project.color),
                      }}
                    />
                  </div>
                  <strong>{projectProgress(project)}% kész</strong>
                </div>
              )}
              <div className="view-toolbar">
                <div className="view-tabs">
                  {(
                    [
                      { key: "board", icon: LayoutGrid, label: "Tábla" },
                      { key: "list", icon: List, label: "Lista" },
                      { key: "calendar", icon: CalendarDays, label: "Naptár" },
                    ] as const
                  ).map((v) => (
                    <button
                      key={v.key}
                      className={currentView === v.key ? "active" : ""}
                      disabled={appearance.saving}
                      onClick={() => {
                        setView(v.key === "calendar" ? "calendar" : null);
                        if (v.key !== "calendar")
                          chooseAppearance({ default_view: v.key });
                        if (page === "calendar") setPage("projects");
                      }}
                    >
                      <v.icon size={16} />
                      {v.label}
                    </button>
                  ))}
                </div>
                <div className="toolbar-actions">
                  <span className="task-count">{filtered.length} feladat</span>
                  <button
                    className={
                      "btn secondary compact " + (filtersOpen ? "selected" : "")
                    }
                    onClick={() => setFiltersOpen(!filtersOpen)}
                  >
                    <SlidersHorizontal size={15} />
                    Szűrők
                    {(memberFilter ||
                      priorityFilter ||
                      statusFilter ||
                      (currentView !== "list" && !showDone)) && (
                      <span className="filter-dot" />
                    )}
                  </button>
                  <button
                    className="icon-btn"
                    disabled={refreshing}
                    aria-label="Frissítés"
                    onClick={async () => {
                      setRefreshing(true);
                      try {
                        await reload();
                        showToast("Munkatér frissítve");
                      } catch (e) {
                        showToast((e as Error).message);
                      } finally {
                        setRefreshing(false);
                      }
                    }}
                  >
                    <RefreshCw size={16} className={refreshing ? "spin" : ""} />
                  </button>
                </div>
              </div>
              {currentView === "list" && (
                <div className="list-controls">
                  <label>
                    Rendezés
                    <select
                      value={appearance.list_sort}
                      disabled={appearance.saving}
                      onChange={(event) =>
                        chooseAppearance({
                          list_sort: event.target.value as ListSort,
                        })
                      }
                    >
                      <option value="due">Határidő szerint</option>
                      <option value="priority">Prioritás szerint</option>
                      <option value="created">Létrehozás: legújabb elöl</option>
                      <option value="manual">Saját kézi sorrend</option>
                    </select>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={visibleCompleted || statusFilter === "done"}
                      disabled={appearance.saving}
                      onChange={(event) =>
                        changeCompleted(event.target.checked)
                      }
                    />
                    Kész feladatok is
                  </label>
                  <span>Automatikusan a fiókodhoz mentve</span>
                </div>
              )}
              {filtersOpen && (
                <div className="filter-panel">
                  <label>
                    Felelős
                    <select
                      value={memberFilter}
                      onChange={(e) => setMemberFilter(e.target.value)}
                    >
                      <option value="">Mindenki</option>
                      {data.members.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.name}
                        </option>
                      ))}
                      <option value="none">Nincs felelős</option>
                    </select>
                  </label>
                  <label>
                    Prioritás
                    <select
                      value={priorityFilter}
                      onChange={(e) => setPriorityFilter(e.target.value)}
                    >
                      <option value="">Összes prioritás</option>
                      {Object.entries(priorities).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Állapot
                    <select
                      value={statusFilter}
                      onChange={(e) => {
                        setStatusFilter(e.target.value);
                      }}
                    >
                      <option value="">Összes állapot</option>
                      {statuses.map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {currentView !== "list" && (
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={visibleCompleted || statusFilter === "done"}
                        onChange={(e) => changeCompleted(e.target.checked)}
                      />
                      Kész feladatok is
                    </label>
                  )}
                  <button
                    className="text-btn"
                    onClick={() => {
                      setMemberFilter("");
                      setPriorityFilter("");
                      setStatusFilter("");
                      if (currentView !== "list") setShowDone(true);
                    }}
                  >
                    Alaphelyzet
                  </button>
                </div>
              )}
              {currentView === "board" ? (
                <div className="kanban-board">
                  {statuses.map((s) => (
                    <section
                      key={s.key}
                      className="kanban-column"
                      onDragOver={(e) => {
                        if (!project?.archived) {
                          e.preventDefault();
                          e.currentTarget.classList.add("drag-over");
                        }
                      }}
                      onDragLeave={(e) =>
                        e.currentTarget.classList.remove("drag-over")
                      }
                      onDrop={(e) => {
                        e.preventDefault();
                        e.currentTarget.classList.remove("drag-over");
                        const t = data.tasks.find(
                          (t) => t.id === e.dataTransfer.getData("text/plain"),
                        );
                        if (t && t.status !== s.key) updateStatus(t, s.key);
                      }}
                    >
                      <div className="column-heading">
                        <span
                          className="column-status"
                          style={{ background: projectDisplayColor(s.color) }}
                        />
                        <h2>{s.label}</h2>
                        <span className="column-count">
                          {filtered.filter((t) => t.status === s.key).length}
                        </span>
                        <button
                          className="icon-btn small"
                          aria-label={`Új feladat: ${s.label}`}
                          onClick={() => createTask(s.key)}
                          disabled={project?.archived}
                        >
                          <Plus size={16} />
                        </button>
                      </div>
                      <div className="column-tasks">
                        {filtered
                          .filter((t) => t.status === s.key)
                          .map((t) => (
                            <TaskCard
                              key={t.id}
                              task={t}
                              data={data}
                              onOpen={() => setTaskEditor({ id: t.id })}
                              onToggle={() =>
                                updateStatus(
                                  t,
                                  t.status === "done" ? "todo" : "done",
                                )
                              }
                              hideProject={!!projectId}
                              readOnly={project?.archived}
                            />
                          ))}
                        <button
                          className="add-card"
                          onClick={() => createTask(s.key)}
                          disabled={project?.archived}
                        >
                          <Plus size={15} />
                          Feladat hozzáadása
                        </button>
                      </div>
                    </section>
                  ))}
                </div>
              ) : currentView === "list" ? (
                <TaskList
                  tasks={listTasks}
                  data={data}
                  manual={appearance.list_sort === "manual"}
                  readOnly={!!project?.archived}
                  onOpen={(task) => setTaskEditor({ id: task.id })}
                  onToggle={(task) =>
                    updateStatus(task, task.status === "done" ? "todo" : "done")
                  }
                  onProject={(id) => go("projects", id)}
                  onMove={async (id, target, placement) => {
                    try {
                      const order = await api<ListOrder>(
                        "list-order/",
                        "PATCH",
                        {
                          task_id: id,
                          target_id: target,
                          placement,
                          version: data.list_order.version,
                        },
                      );
                      setData((previous) =>
                        previous
                          ? { ...previous, list_order: order }
                          : previous,
                      );
                      await reload();
                    } catch (error) {
                      await reload().catch(() => {});
                      throw error;
                    }
                  }}
                />
              ) : (
                <CalendarView
                  tasks={filtered}
                  data={data}
                  onOpen={(t) => setTaskEditor({ id: t.id })}
                />
              )}
            </>
          )}
          <footer className="app-footer">
            <span className="footer-mark">kjbk projekt guru</span>
            <span>Egy helyen. Egy irányba.</span>
            <span className="footer-right">
              <span />
              Közös munkatér
            </span>
          </footer>
        </main>
      </div>
      <nav className="mobile-bottom-nav">
        <button
          className={page === "overview" ? "active" : ""}
          onClick={() => go("overview")}
        >
          <LayoutDashboard size={20} />
          <span>Áttekintés</span>
        </button>
        <button
          className={page === "projects" ? "active" : ""}
          onClick={() => go("projects")}
        >
          <FolderKanban size={20} />
          <span>Projektek</span>
        </button>
        <button
          className="mobile-add"
          onClick={() => createTask()}
          aria-label="Új feladat"
        >
          <Plus size={25} />
        </button>
        <button
          className={page === "mine" ? "active" : ""}
          onClick={() => go("mine")}
        >
          <CircleCheck size={20} />
          <span>Saját</span>
        </button>
        <button
          className={page === "calendar" ? "active" : ""}
          onClick={() => go("calendar")}
        >
          <CalendarDays size={20} />
          <span>Naptár</span>
        </button>
      </nav>
      {noticesOpen && (
        <>
          <div
            className="popover-scrim"
            onClick={() => setNoticesOpen(false)}
          />
          <aside className="notification-panel">
            <div className="notification-heading">
              <h2>
                Értesítések <span>{data.unread}</span>
              </h2>
              <button
                className="icon-btn"
                aria-label="Bezárás"
                onClick={() => setNoticesOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            {data.unread > 0 && (
              <button
                className="text-btn read-all"
                onClick={async () => {
                  try {
                    await api("notifications/read/", "POST");
                    await reload();
                  } catch (e) {
                    showToast((e as Error).message);
                  }
                }}
              >
                <CheckCheck size={15} />
                Mindet olvasottnak jelölöm
              </button>
            )}
            <div className="notification-list">
              {data.notifications.length ? (
                data.notifications.map((n) => (
                  <button
                    key={n.id}
                    className={"notice " + (!n.read ? "unread" : "")}
                    onClick={async () => {
                      try {
                        await api("notifications/read/", "POST", { id: n.id });
                        await reload();
                        if (n.task_id) setTaskEditor({ id: n.task_id });
                        setNoticesOpen(false);
                      } catch (e) {
                        showToast((e as Error).message);
                      }
                    }}
                  >
                    <span className="notice-icon">
                      <Bell size={17} />
                    </span>
                    <div>
                      <strong>{n.title}</strong>
                      <p>{n.body}</p>
                      <time>{relative(n.created_at)}</time>
                    </div>
                    {!n.read && <i />}
                  </button>
                ))
              ) : (
                <div className="empty-small">
                  <Bell size={30} />
                  <h3>Egyelőre csend van.</h3>
                  <p>Az új feladatok és határidők itt jelennek meg.</p>
                </div>
              )}
            </div>
            <button
              className="notification-settings"
              onClick={() => {
                setNoticesOpen(false);
                setSettingsInitialTab("notifications");
                setSettingsOpen(true);
              }}
            >
              <Settings2 size={15} />
              Értesítési beállítások
            </button>
          </aside>
        </>
      )}
      {taskEditor && (
        <TaskPanel
          key={taskEditor.id || "new"}
          id={taskEditor.id}
          initialProject={projectId || undefined}
          initialStatus={taskEditor.status}
          data={data}
          onClose={() => setTaskEditor(null)}
          onSaved={reload}
          toast={showToast}
        />
      )}
      {projectEditor && (
        <ProjectEditor
          project={projectEditor}
          onClose={() => setProjectEditor(null)}
          toast={showToast}
          onSaved={async (p) => {
            await reload();
            go("projects", p.id);
            setProjectEditor(null);
          }}
        />
      )}
      {settingsOpen && (
        <Settings
          data={data}
          initialTab={settingsInitialTab}
          onClose={() => {
            setSettingsOpen(false);
            setSettingsInitialTab("connections");
            if (location.search) history.replaceState(null, "", "/");
          }}
          reload={reload}
          toast={showToast}
          onLogout={async () => {
            try {
              if ("serviceWorker" in navigator) {
                const reg = await navigator.serviceWorker.getRegistration("/");
                const sub = await reg?.pushManager?.getSubscription();
                if (sub) {
                  await api("push/", "DELETE", sub.toJSON());
                  await sub.unsubscribe();
                }
              }
              await api("logout/", "POST");
              resetAppearance();
              setSettingsOpen(false);
              setData(null);
              setSession(null);
              await api("session/");
            } catch (e) {
              showToast((e as Error).message);
            }
          }}
        />
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
          <button aria-label="Bezárás" onClick={() => setToast("")}>
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function TaskCard({
  task: t,
  data,
  onOpen,
  onToggle,
  hideProject,
  readOnly,
}: {
  task: Task;
  data: Bootstrap;
  onOpen: () => void;
  onToggle: () => void;
  hideProject: boolean;
  readOnly?: boolean;
}) {
  const p = data.projects.find((p) => p.id === t.project_id),
    late = isOverdue(t);
  return (
    <article
      className={"task-card " + (t.status === "done" ? "is-done" : "")}
      draggable={!readOnly}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", t.id)}
    >
      <div className="task-card-labels">
        {t.labels.map((l, i) => (
          <span className={"label-tag label-" + (i % 4)} key={l}>
            {l}
          </span>
        ))}
        {t.priority === "urgent" || t.priority === "high" ? (
          <span
            className={"card-priority " + t.priority}
            title={priorities[t.priority]}
          >
            <ArrowUp size={13} />
            {priorities[t.priority]}
          </span>
        ) : null}
      </div>
      <button className="card-title" onClick={onOpen}>
        {t.title}
      </button>
      {!hideProject && (
        <button className="card-project" onClick={onOpen}>
          <span style={{ background: projectDisplayColor(p?.color) }} />
          {p?.name}
        </button>
      )}
      {t.checklist.length > 0 && (
        <div className="card-checklist">
          <div className="mini-progress">
            <span
              style={{
                width: `${(t.checklist.filter((c) => c.done).length / t.checklist.length) * 100}%`,
              }}
            />
          </div>
          <span>
            <CheckCheck size={13} />
            {t.checklist.filter((c) => c.done).length}/{t.checklist.length}
          </span>
        </div>
      )}
      <div className="card-bottom">
        <div className="card-bottom-left">
          <StatusMark
            value={t.status}
            onClick={() => !readOnly && onToggle()}
          />
          {t.due_date && (
            <span className={"card-date " + (late ? "overdue" : "")}>
              <CalendarDays size={12} />
              {dayLabel(t.due_date)}
              {t.due_time && " · " + t.due_time}
            </span>
          )}
          {t.calendar?.enabled && (
            <CalendarCheck size={13} className="calendar-check" />
          )}
          {t.comment_count > 0 && (
            <span className="card-count">
              <MessageSquare size={12} />
              {t.comment_count}
            </span>
          )}
          {t.attachment_count > 0 && (
            <span className="card-count">
              <Paperclip size={12} />
              {t.attachment_count}
            </span>
          )}
        </div>
        <Avatar
          user={data.members.find((u) => u.id === t.assignee_id)}
          size="tiny"
        />
      </div>
    </article>
  );
}

function CalendarView({
  tasks,
  data,
  onOpen,
}: {
  tasks: Task[];
  data: Bootstrap;
  onOpen: (t: Task) => void;
}) {
  const [month, setMonth] = useState(() => new Date(today() + "T12:00:00")),
    [selected, setSelected] = useState(today());
  const dateString = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const first = new Date(month.getFullYear(), month.getMonth(), 1),
    offset = (first.getDay() + 6) % 7,
    start = new Date(first);
  start.setDate(1 - offset);
  const days = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
  const dated = tasks.filter((t) => t.due_date),
    selectedTasks = dated.filter((t) => t.due_date === selected);
  return (
    <section className="calendar-view">
      <div className="calendar-toolbar">
        <h2>
          {new Intl.DateTimeFormat("hu-HU", {
            year: "numeric",
            month: "long",
          }).format(month)}
        </h2>
        <div className="button-row">
          <button
            className="btn secondary compact"
            onClick={() => {
              setMonth(new Date(today() + "T12:00:00"));
              setSelected(today());
            }}
          >
            Ma
          </button>
          <button
            className="icon-btn"
            aria-label="Előző hónap"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
            }
          >
            <ChevronLeft size={18} />
          </button>
          <button
            className="icon-btn"
            aria-label="Következő hónap"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
            }
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
      <div className="calendar-weekdays">
        {["H", "K", "Sze", "Cs", "P", "Szo", "V"].map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div className="calendar-grid">
        {days.map((d) => {
          const key = dateString(d),
            ts = dated.filter((t) => t.due_date === key);
          return (
            <div
              className={
                "calendar-day " +
                (d.getMonth() !== month.getMonth() ? "outside " : "") +
                (key === today() ? "today " : "") +
                (key === selected ? "chosen" : "")
              }
              key={key}
            >
              <button
                className="day-number"
                aria-label={`${key}, ${ts.length} feladat`}
                onClick={() => setSelected(key)}
              >
                {d.getDate()}
              </button>
              <div className="calendar-day-tasks">
                {ts.slice(0, 3).map((t) => (
                  <button
                    key={t.id}
                    className={
                      "calendar-task " +
                      (t.status === "done" ? "completed" : "")
                    }
                    style={{
                      borderLeftColor: projectDisplayColor(
                        data.projects.find((p) => p.id === t.project_id)?.color,
                      ),
                    }}
                    onClick={() => onOpen(t)}
                  >
                    {t.due_time && <strong>{t.due_time} </strong>}
                    {t.title}
                  </button>
                ))}
                {ts.length > 3 && (
                  <button
                    className="calendar-more"
                    onClick={() => setSelected(key)}
                  >
                    +{ts.length - 3} további
                  </button>
                )}
              </div>
              <div className="mobile-day-dots">
                {ts.slice(0, 4).map((t) => (
                  <i
                    key={t.id}
                    style={{
                      background: projectDisplayColor(
                        data.projects.find((p) => p.id === t.project_id)?.color,
                      ),
                    }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div className="calendar-agenda">
        <div className="section-heading">
          <h3>
            {new Intl.DateTimeFormat("hu-HU", {
              month: "long",
              day: "numeric",
              weekday: "long",
            }).format(new Date(selected + "T12:00:00"))}
          </h3>
          <span>{selectedTasks.length} feladat</span>
        </div>
        {selectedTasks.length ? (
          selectedTasks
            .sort((a, b) => (a.due_time || "").localeCompare(b.due_time || ""))
            .map((t) => (
              <button
                className="agenda-task"
                key={t.id}
                onClick={() => onOpen(t)}
              >
                <span className="agenda-time">{t.due_time || "Egész nap"}</span>
                <span
                  className="project-dot"
                  style={{
                    background: projectDisplayColor(
                      data.projects.find((p) => p.id === t.project_id)?.color,
                    ),
                  }}
                />
                <strong>{t.title}</strong>
                <Avatar
                  user={data.members.find((u) => u.id === t.assignee_id)}
                  size="small"
                />
                <ChevronRight size={16} />
              </button>
            ))
        ) : (
          <p className="muted agenda-empty">
            Erre a napra nincs határidős feladat.
          </p>
        )}
      </div>
      {tasks.some((t) => !t.due_date) && (
        <p className="calendar-footnote">
          {tasks.filter((t) => !t.due_date).length} feladatnak még nincs
          határideje. Ezeket a Tábla vagy Lista nézetben találod.
        </p>
      )}
    </section>
  );
}

function ProjectEditor({
  project,
  onClose,
  onSaved,
  toast,
}: {
  project: Project | "new";
  onClose: () => void;
  onSaved: (p: Project) => Promise<void>;
  toast: (s: string) => void;
}) {
  const existing = project !== "new" ? project : null;
  const [name, setName] = useState(existing?.name || ""),
    [description, setDescription] = useState(existing?.description || ""),
    [color, setColor] = useState(existing?.color || "#462773"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const colors = [
    "#462773",
    "#e52053",
    "#ee5a1e",
    "#9a97a3",
    "#1fa463",
    "#f5a623",
  ];
  return (
    <Modal
      title={existing ? "Projekt szerkesztése" : "Új közös projekt"}
      onClose={onClose}
    >
      <form
        className="project-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const r = await api<{ project: Project }>(
              existing ? `projects/${existing.id}/` : "projects/",
              existing ? "PATCH" : "POST",
              { name, description, color },
            );
            await onSaved(r.project);
            toast(existing ? "Projekt frissítve" : "Indulhat a közös munka!");
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {error && <div className="error-banner">{error}</div>}
        <label>
          Projekt neve
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Mi a következő közös cél?"
            required
            autoFocus
            maxLength={120}
          />
        </label>
        <label>
          Rövid leírás
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Miről szól ez a projekt?"
            rows={3}
            maxLength={5000}
          />
        </label>
        <label>Projekt színe</label>
        <div className="color-picker">
          {colors.map((c) => (
            <button
              type="button"
              key={c}
              style={{ background: c }}
              aria-label={`Szín: ${c}`}
              aria-pressed={color === c}
              onClick={() => setColor(c)}
            >
              {color === c && <Check size={18} />}
            </button>
          ))}
        </div>
        <div className="modal-footer">
          {existing ? (
            <button
              type="button"
              className="text-btn danger"
              disabled={busy}
              onClick={async () => {
                if (
                  !confirm(
                    existing.archived
                      ? "Visszaállítod a projektet?"
                      : "Archiválod a projektet? A feladatok megmaradnak, de csak olvashatók lesznek.",
                  )
                )
                  return;
                setBusy(true);
                try {
                  const r = await api<{ project: Project }>(
                    `projects/${existing.id}/`,
                    "PATCH",
                    { archived: !existing.archived },
                  );
                  await onSaved(r.project);
                  toast(
                    existing.archived
                      ? "Projekt visszaállítva"
                      : "Projekt archiválva",
                  );
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Archive size={15} />
              {existing.archived ? "Visszaállítás" : "Archiválás"}
            </button>
          ) : (
            <span />
          )}
          <button className="btn primary" disabled={busy}>
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Plus size={16} />
            )}{" "}
            {existing ? "Mentés" : "Projekt létrehozása"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
