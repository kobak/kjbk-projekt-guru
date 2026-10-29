import { useEffect, useState } from "react";
import {
  CalendarPlus,
  CalendarCheck,
  ExternalLink,
  Paperclip,
  Send,
  Trash2,
  Plus,
  X,
  Check,
  LoaderCircle,
  Circle,
} from "lucide-react";
import type { Bootstrap, Task, Status } from "./types";
import { api, ApiError, dayLabel, relative } from "./api";
import { Avatar, Modal, statuses, priorities } from "./ui";

type Props = {
  id: string | null;
  initialProject?: string;
  initialStatus?: Status;
  data: Bootstrap;
  onClose: () => void;
  onSaved: () => Promise<void>;
  toast: (s: string) => void;
};
export default function TaskPanel({
  id,
  initialProject,
  initialStatus,
  data,
  onClose,
  onSaved,
  toast,
}: Props) {
  const [task, setTask] = useState<Task | null>(null),
    [loading, setLoading] = useState(!!id),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [project, setProject] = useState(
      initialProject || data.projects.find((p) => !p.archived)?.id || "",
    );
  const [status, setStatus] = useState<Status>(initialStatus || "todo"),
    [priority, setPriority] = useState<Task["priority"]>("normal"),
    [assignee, setAssignee] = useState(""),
    [dueDate, setDueDate] = useState(""),
    [dueTime, setDueTime] = useState(""),
    [labels, setLabels] = useState("");
  const [comment, setComment] = useState(""),
    [check, setCheck] = useState(""),
    [tab, setTab] = useState("details"),
    [editVersion, setEditVersion] = useState(0),
    [conflict, setConflict] = useState(false);
  const applyFields = (t: Task) => {
    setTitle(t.title);
    setDescription(t.description);
    setProject(t.project_id);
    setStatus(t.status);
    setPriority(t.priority);
    setAssignee(String(t.assignee_id || ""));
    setDueDate(t.due_date || "");
    setDueTime(t.due_time || "");
    setLabels(t.labels.join(", "));
    setEditVersion(t.version);
    setConflict(false);
  };
  const load = async () => {
    if (!id) return;
    const r = await api<{ task: Task }>(`tasks/${id}/`);
    setTask(r.task);
    return r.task;
  };
  useEffect(() => {
    let alive = true;
    if (!id) return;
    api<{ task: Task }>(`tasks/${id}/`)
      .then(({ task: t }) => {
        if (!alive) return;
        setTask(t);
        applyFields(t);
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [id]);
  const mutate = async (fn: () => Promise<unknown>, message?: string) => {
    setError("");
    setBusy(true);
    try {
      await fn();
      await load();
      await onSaved();
      if (message) toast(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(id ? `tasks/${id}/` : "tasks/", id ? "PATCH" : "POST", {
        title,
        description,
        project_id: project,
        status,
        priority,
        assignee_id: assignee ? Number(assignee) : null,
        due_date: dueDate || null,
        due_time: dueDate && dueTime ? dueTime : null,
        labels: labels
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        ...(task ? { version: editVersion } : {}),
      });
      await onSaved();
      toast(id ? "Változtatások elmentve" : "A feladat elkészült");
      onClose();
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 409) setConflict(true);
    } finally {
      setBusy(false);
    }
  };
  const archived = data.projects.find((p) => p.id === project)?.archived;
  const closeEditor = () => {
    const changed = task
      ? title !== task.title ||
        description !== task.description ||
        project !== task.project_id ||
        status !== task.status ||
        priority !== task.priority ||
        assignee !== String(task.assignee_id || "") ||
        dueDate !== (task.due_date || "") ||
        dueTime !== (task.due_time || "") ||
        labels !== task.labels.join(", ")
      : !!(title || description || labels || dueDate || assignee);
    if (
      !changed ||
      confirm("Bezárod mentés nélkül? A mezők módosításai elvesznek.")
    )
      onClose();
  };
  return (
    <Modal
      title={id ? "Feladat részletei" : "Új feladat"}
      onClose={closeEditor}
      wide
    >
      {loading ? (
        <div className="loading">
          <LoaderCircle className="spin" />
          Feladat betöltése…
        </div>
      ) : (
        <>
          <div className="task-tabs">
            <button
              className={tab === "details" ? "active" : ""}
              onClick={() => setTab("details")}
            >
              Részletek
            </button>
            <button
              className={tab === "conversation" ? "active" : ""}
              onClick={() => setTab("conversation")}
              disabled={!id}
            >
              Hozzászólások{" "}
              {task?.comment_count ? `(${task.comment_count})` : ""}
            </button>
            <button
              className={tab === "files" ? "active" : ""}
              onClick={() => setTab("files")}
              disabled={!id}
            >
              Fájlok{" "}
              {task?.attachment_count ? `(${task.attachment_count})` : ""}
            </button>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              {conflict && (
                <button
                  type="button"
                  className="text-btn"
                  onClick={async () => {
                    if (
                      !confirm(
                        "Betöltöd az aktuális változatot? A még nem mentett mezőmódosítások elvesznek.",
                      )
                    )
                      return;
                    try {
                      const t = await load();
                      if (t) {
                        applyFields(t);
                        setError("");
                      }
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Aktuális változat betöltése
                </button>
              )}
            </div>
          )}
          {tab === "details" && (
            <form onSubmit={save} className="task-form">
              <label className="sr-only" htmlFor="task-title">
                Feladat neve
              </label>
              <input
                id="task-title"
                className="task-title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Mit szeretnénk megcsinálni?"
                maxLength={250}
                required
                autoFocus={!id}
                disabled={archived}
              />
              <div className="form-grid">
                <label>
                  Projekt
                  <select
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                    required
                    disabled={archived}
                  >
                    {!project && <option value="">Válassz projektet</option>}
                    {data.projects
                      .filter((p) => !p.archived || p.id === project)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Állapot
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value as Status)}
                    disabled={archived}
                  >
                    {statuses.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Felelős
                  <select
                    value={assignee}
                    onChange={(e) => setAssignee(e.target.value)}
                    disabled={archived}
                  >
                    <option value="">Még nincs felelős</option>
                    {data.members.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                        {u.id === data.user.id ? " (én)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Prioritás
                  <select
                    value={priority}
                    onChange={(e) =>
                      setPriority(e.target.value as Task["priority"])
                    }
                    disabled={archived}
                  >
                    {Object.entries(priorities).map(([key, name]) => (
                      <option key={key} value={key}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Határidő
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    disabled={archived}
                  />
                </label>
                <label>
                  Időpont <span className="muted">· nem kötelező</span>
                  <input
                    type="time"
                    value={dueTime}
                    onChange={(e) => setDueTime(e.target.value)}
                    disabled={!dueDate || archived}
                  />
                </label>
              </div>
              <label>
                Leírás
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Minden, amit a feladathoz tudnunk kell…"
                  rows={4}
                  maxLength={20000}
                  disabled={archived}
                />
              </label>
              <label>
                Címkék <span className="muted">· vesszővel elválasztva</span>
                <input
                  value={labels}
                  onChange={(e) => setLabels(e.target.value)}
                  placeholder="pl. Design, Fejlesztés"
                  disabled={archived}
                />
              </label>
              {id && (
                <section className="checklist-section">
                  <h3>
                    Részfeladatok{" "}
                    <span className="muted">
                      {task?.checklist.filter((c) => c.done).length}/
                      {task?.checklist.length}
                    </span>
                  </h3>
                  {task?.checklist.map((c) => (
                    <div className="checklist-row" key={c.id}>
                      <button
                        type="button"
                        className={"check-box " + (c.done ? "checked" : "")}
                        aria-label={c.done ? "Visszanyitás" : "Készre jelölés"}
                        disabled={busy || archived}
                        onClick={() =>
                          mutate(() =>
                            api(`tasks/${id}/checklist/${c.id}/`, "PATCH", {
                              done: !c.done,
                            }),
                          )
                        }
                      >
                        {c.done && <Check size={13} />}
                      </button>
                      <span className={c.done ? "strike" : ""}>{c.text}</span>
                      <button
                        type="button"
                        className="icon-btn small"
                        aria-label="Részfeladat törlése"
                        disabled={busy || archived}
                        onClick={() =>
                          mutate(() =>
                            api(`tasks/${id}/checklist/${c.id}/`, "DELETE"),
                          )
                        }
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                  {!archived && (
                    <div className="inline-add">
                      <Plus size={16} />
                      <input
                        value={check}
                        onChange={(e) => setCheck(e.target.value)}
                        placeholder="Új részfeladat…"
                        maxLength={250}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            if (check.trim())
                              mutate(async () => {
                                await api(`tasks/${id}/checklist/`, "POST", {
                                  text: check,
                                });
                                setCheck("");
                              });
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="text-btn"
                        disabled={busy || !check.trim()}
                        onClick={() =>
                          mutate(async () => {
                            await api(`tasks/${id}/checklist/`, "POST", {
                              text: check,
                            });
                            setCheck("");
                          })
                        }
                      >
                        Hozzáadás
                      </button>
                    </div>
                  )}
                </section>
              )}
              {id && (
                <div
                  className={
                    "calendar-box " +
                    (!data.integrations.google_connected ? "manual" : "")
                  }
                >
                  <div className="calendar-box-icon">
                    {task?.calendar?.enabled ? (
                      <CalendarCheck size={22} />
                    ) : (
                      <CalendarPlus size={22} />
                    )}
                  </div>
                  <div>
                    <strong>Saját Google Naptár</strong>
                    <p>
                      {task?.calendar?.enabled
                        ? task.calendar.error ||
                          (task.calendar.pending
                            ? "Szinkronizálás folyamatban…"
                            : `A naptáradban · ${dayLabel(task.due_date)}`)
                        : data.integrations.google_connected
                          ? "A határidőt tedd a saját naptáradba."
                          : "A megnyíló naptárban véglegesítheted az eseményt."}
                    </p>
                  </div>
                  {task?.calendar?.enabled ? (
                    <div className="calendar-actions">
                      {task.calendar.url && (
                        <a
                          href={task.calendar.url}
                          target="_blank"
                          rel="noreferrer"
                          className="icon-btn"
                          aria-label="Esemény megnyitása"
                        >
                          <ExternalLink size={16} />
                        </a>
                      )}
                      <button
                        type="button"
                        className="text-btn"
                        disabled={busy}
                        onClick={() =>
                          mutate(async () => {
                            const r = await api<{ ok: boolean; error: string }>(
                              `tasks/${id}/calendar/`,
                              "DELETE",
                            );
                            if (!r.ok) throw new Error(r.error);
                          }, "Eltávolítva a naptáradból")
                        }
                      >
                        Eltávolítás
                      </button>
                    </div>
                  ) : !data.integrations.google_connected ? (
                    <div className="calendar-actions manual-calendar-actions">
                      {task?.calendar_manual_url ? (
                        <a
                          className="btn secondary compact"
                          href={task.calendar_manual_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <CalendarPlus size={15} />
                          Mentés a Google Naptárba
                          <ExternalLink size={12} />
                        </a>
                      ) : (
                        <button
                          type="button"
                          className="btn secondary compact"
                          disabled
                        >
                          Előbb adj meg határidőt
                        </button>
                      )}
                      {task?.calendar_ics_url && (
                        <a
                          className="text-btn"
                          href={task.calendar_ics_url}
                          download
                        >
                          Másik naptár (.ics)
                        </a>
                      )}
                      <p className="manual-calendar-hint">
                        Egyszeri mentés. Automatikus frissítéshez csatlakoztasd
                        a naptáradat a Beállításokban.
                      </p>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn secondary compact"
                      disabled={busy || !task?.due_date}
                      onClick={() =>
                        mutate(async () => {
                          const r = await api<{ ok: boolean; error: string }>(
                            `tasks/${id}/calendar/`,
                            "POST",
                          );
                          if (!r.ok) throw new Error(r.error);
                        }, "A feladat a saját naptáradba került")
                      }
                    >
                      Naptárba
                    </button>
                  )}
                </div>
              )}
              {!id && (
                <p className="form-hint">
                  <CalendarPlus size={15} />
                  Mentés után hozzáadhatod a saját naptáradhoz, és fájlokat is
                  csatolhatsz.
                </p>
              )}
              <div className="modal-footer">
                {id && !archived ? (
                  <button
                    type="button"
                    className="text-btn danger"
                    disabled={busy}
                    onClick={async () => {
                      if (
                        confirm(
                          "Törlöd ezt a feladatot? A kapcsolódó naptáreseményeket is eltávolítjuk.",
                        )
                      ) {
                        setBusy(true);
                        try {
                          await api(`tasks/${id}/`, "DELETE", {
                            version: editVersion,
                          });
                          await onSaved();
                          toast("Feladat törölve");
                          onClose();
                        } catch (e) {
                          setError((e as Error).message);
                          if (e instanceof ApiError && e.status === 409)
                            setConflict(true);
                        } finally {
                          setBusy(false);
                        }
                      }
                    }}
                  >
                    <Trash2 size={15} />
                    Törlés
                  </button>
                ) : (
                  <span />
                )}
                <div className="button-row">
                  <button
                    type="button"
                    className="btn secondary"
                    onClick={closeEditor}
                  >
                    Bezárás
                  </button>
                  {!archived && (
                    <button className="btn primary" disabled={busy || !project}>
                      {busy ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <Check size={16} />
                      )}{" "}
                      {id ? "Mentés" : "Feladat létrehozása"}
                    </button>
                  )}
                </div>
              </div>
            </form>
          )}
          {tab === "conversation" && (
            <div className="conversation">
              <div className="comment-list">
                {task?.comments?.length ? (
                  task.comments.map((c) => (
                    <article className="comment" key={c.id}>
                      <Avatar user={c.user} />
                      <div>
                        <div className="comment-meta">
                          <strong>{c.user.name}</strong>
                          <span>{relative(c.created_at)}</span>
                        </div>
                        <p>{c.body}</p>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="empty-small">
                    <Circle size={28} />
                    <h3>Beszéljük meg itt.</h3>
                    <p>
                      A feladathoz kapcsolódó gondolatok egy helyen maradnak.
                    </p>
                  </div>
                )}
              </div>
              {!archived && (
                <form
                  className="comment-compose"
                  onSubmit={(e) => {
                    e.preventDefault();
                    mutate(async () => {
                      await api(`tasks/${id}/comments/`, "POST", {
                        body: comment,
                      });
                      setComment("");
                    }, "Hozzászólás elküldve");
                  }}
                >
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Írj hozzászólást…"
                    required
                    maxLength={10000}
                    rows={3}
                  />
                  <button
                    className="btn primary"
                    disabled={busy || !comment.trim()}
                  >
                    <Send size={16} />
                    Küldés
                  </button>
                </form>
              )}
            </div>
          )}
          {tab === "files" && (
            <div className="files-section">
              {!archived && (
                <label className={"upload-box " + (busy ? "disabled" : "")}>
                  <Paperclip size={26} />
                  <strong>Fájl csatolása</strong>
                  <span>Kattints a kiválasztáshoz · legfeljebb 25 MB</span>
                  <input
                    type="file"
                    className="sr-only"
                    disabled={busy}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        if (file.size > 25 * 1024 * 1024) {
                          setError("A fájl legfeljebb 25 MB lehet.");
                          return;
                        }
                        const form = new FormData();
                        form.append("file", file);
                        mutate(
                          () => api(`tasks/${id}/attachments/`, "POST", form),
                          "Fájl feltöltve",
                        );
                      }
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
              {task?.attachments?.map((a) => (
                <div className="attachment-row" key={a.id}>
                  <div className="attachment-icon">
                    <Paperclip size={20} />
                  </div>
                  <a href={a.url}>
                    <strong>{a.name}</strong>
                    <span>
                      {a.size < 1024 * 1024
                        ? `${Math.ceil(a.size / 1024)} KB`
                        : `${(a.size / 1024 / 1024).toFixed(1)} MB`}
                    </span>
                  </a>
                  <button
                    className="icon-btn"
                    aria-label="Fájl törlése"
                    disabled={busy}
                    onClick={() => {
                      if (confirm("Törlöd ezt a csatolmányt?"))
                        mutate(
                          () => api(`attachments/${a.id}/`, "DELETE"),
                          "Csatolmány törölve",
                        );
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {!task?.attachments?.length && (
                <p className="muted center">Még nincs csatolt fájl.</p>
              )}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
