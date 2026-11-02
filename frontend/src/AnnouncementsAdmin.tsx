import { useEffect, useState } from "react";
import {
  Check,
  Eye,
  EyeOff,
  LoaderCircle,
  Megaphone,
  Pencil,
  Plus,
  RefreshCw,
} from "lucide-react";
import { api, ApiError } from "./api";
import type { AdminAnnouncement } from "./types";
import AnnouncementCard from "./AnnouncementCard";

type Content = Pick<
  AdminAnnouncement,
  "title" | "body" | "link_label" | "link_url"
>;
const blank: Content = { title: "", body: "", link_label: "", link_url: "" };

export default function AnnouncementsAdmin({
  onChanged,
  toast,
}: {
  onChanged: () => Promise<void>;
  toast: (message: string) => void;
}) {
  const [items, setItems] = useState<AdminAnnouncement[]>([]);
  const [selected, setSelected] = useState<AdminAnnouncement | null>(null);
  const [form, setForm] = useState<Content>(blank);
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [conflict, setConflict] = useState(false);
  const dirty = (Object.keys(blank) as (keyof Content)[]).some(
    (key) => form[key] !== (selected?.[key] || ""),
  );
  const refresh = async () => {
    const value = await api<{ announcements: AdminAnnouncement[] }>(
      "announcements/",
    );
    setItems(value.announcements);
    return value.announcements;
  };
  useEffect(() => {
    let alive = true;
    api<{ announcements: AdminAnnouncement[] }>("announcements/")
      .then((value) => {
        if (alive) setItems(value.announcements);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  const edit = (item: AdminAnnouncement | null) => {
    setSelected(item);
    setForm(
      item
        ? {
            title: item.title,
            body: item.body,
            link_label: item.link_label,
            link_url: item.link_url,
          }
        : blank,
    );
    setError("");
    setConflict(false);
  };
  const run = async (
    operation: () => Promise<{ announcement: AdminAnnouncement }>,
    message: string,
    updateEditor = true,
  ) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setConflict(false);
    try {
      const result = await operation();
      await refresh();
      if (updateEditor) edit(result.announcement);
      else if (selected?.id === result.announcement.id)
        setSelected(result.announcement);
      await onChanged();
      toast(message);
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 409) setConflict(true);
    } finally {
      setBusy(false);
    }
  };
  const publication = (item: AdminAnnouncement) =>
    run(
      () =>
        api(
          `announcements/${item.id}/${item.published ? "unpublish" : "publish"}/`,
          "POST",
          { version: item.version },
        ),
      item.published ? "Hír levéve a kezdőlapról" : "Hír közzétéve a csapatnak",
      false,
    );
  return (
    <section className="announcements-admin" aria-label="Hírek kezelése">
      <div className="settings-intro announcement-admin-intro">
        <div>
          <h3>
            <Megaphone size={20} /> Hírek a csapatnak
          </h3>
          <p>
            Rövid információ a kezdőlapon, weben és a Mac-appban. Egyszerre egy
            hír látható; a tagok a saját fiókjukban elrejthetik.
          </p>
        </div>
        <button
          className="btn secondary compact"
          type="button"
          disabled={busy}
          onClick={() => edit(null)}
        >
          <Plus size={16} />
          Új hír
        </button>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
          {conflict && (
            <button
              className="btn secondary compact"
              type="button"
              onClick={async () => {
                try {
                  const values = await refresh();
                  edit(
                    values.find((value) => value.id === selected?.id) || null,
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <RefreshCw size={14} />
              Szerkesztő újratöltése
            </button>
          )}
        </div>
      )}
      <form
        className="announcement-editor"
        aria-label="Hír szerkesztése"
        onSubmit={(e) => {
          e.preventDefault();
          run(
            () =>
              api(
                selected ? `announcements/${selected.id}/` : "announcements/",
                selected ? "PATCH" : "POST",
                { ...form, ...(selected ? { version: selected.version } : {}) },
              ),
            "Hír elmentve",
          );
        }}
      >
        <label htmlFor="announcement-title">
          Cím
          <input
            id="announcement-title"
            required
            maxLength={120}
            value={form.title}
            disabled={busy}
            placeholder="Például: Megérkezett a GURU Mac-app"
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label htmlFor="announcement-body">
          Rövid szöveg
          <textarea
            id="announcement-body"
            maxLength={500}
            rows={3}
            value={form.body}
            disabled={busy}
            placeholder="A legfontosabb információ, néhány mondatban."
            onChange={(e) => setForm({ ...form, body: e.target.value })}
          />
        </label>
        <div className="announcement-link-fields">
          <label htmlFor="announcement-link-label">
            Gomb felirata · nem kötelező
            <input
              id="announcement-link-label"
              maxLength={50}
              value={form.link_label}
              disabled={busy}
              required={!!form.link_url}
              placeholder="Mac-app letöltése"
              onChange={(e) => setForm({ ...form, link_label: e.target.value })}
            />
          </label>
          <label htmlFor="announcement-link-url">
            Hivatkozás
            <input
              id="announcement-link-url"
              inputMode="url"
              maxLength={2000}
              value={form.link_url}
              disabled={busy}
              required={!!form.link_label}
              placeholder="https://… vagy /?task=…"
              onChange={(e) => setForm({ ...form, link_url: e.target.value })}
            />
          </label>
        </div>
        <p className="form-hint">
          {selected?.published
            ? "A közzétett hír módosítás után ismét megjelenik azoknak is, akik elrejtették."
            : "A mentés vázlatot készít. A Közzététel gomb jeleníti meg a csapatnak, és leveszi a korábbi kiemelt hírt."}
        </p>
        <div className="button-row">
          <button
            className="btn primary compact"
            type="submit"
            disabled={busy || !form.title.trim()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Check size={16} />
            )}
            Mentés
          </button>
        </div>
      </form>
      <div className="announcement-preview">
        <span className="eyebrow">ELŐNÉZET</span>
        <AnnouncementCard
          preview
          announcement={{
            ...form,
            title: form.title || "A hír címe",
            body: form.body || "Itt jelenik meg a rövid információ.",
          }}
        />
      </div>
      <div className="announcement-history">
        <h4>Elmentett hírek</h4>
        {loading ? (
          <p className="form-hint">Hírek betöltése…</p>
        ) : items.length === 0 ? (
          <p className="form-hint">Még nincs elmentett hír.</p>
        ) : (
          items.map((item) => (
            <article className="announcement-admin-row" key={item.id}>
              <div>
                <span
                  className={`announcement-state ${item.published ? "published" : ""}`}
                >
                  {item.published
                    ? "Látható a kezdőlapon"
                    : "Nincs megjelenítve"}
                </span>
                <strong>{item.title}</strong>
                <small>
                  {new Intl.DateTimeFormat("hu-HU", {
                    dateStyle: "medium",
                    timeStyle: "short",
                    timeZone: "Europe/Budapest",
                  }).format(new Date(item.updated_at))}
                </small>
              </div>
              <div className="button-row">
                <button
                  className="btn secondary compact"
                  type="button"
                  disabled={busy}
                  onClick={() => edit(item)}
                >
                  <Pencil size={14} />
                  Szerkesztés
                </button>
                <button
                  className={`btn ${item.published ? "secondary" : "primary"} compact`}
                  type="button"
                  disabled={
                    busy ||
                    (!item.published && selected?.id === item.id && dirty)
                  }
                  title={
                    !item.published && selected?.id === item.id && dirty
                      ? "Előbb mentsd a módosításokat"
                      : undefined
                  }
                  onClick={() => publication(item)}
                >
                  {item.published ? <EyeOff size={14} /> : <Eye size={14} />}
                  {item.published ? "Levétel" : "Közzététel"}
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
