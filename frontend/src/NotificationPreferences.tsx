import { useEffect, useState } from "react";
import { BellRing, Check, LoaderCircle, Mail, RefreshCw } from "lucide-react";
import { api } from "./api";
import type {
  NotificationEvent,
  NotificationPreferences as Preferences,
} from "./types";

export default function NotificationPreferences({
  pushOn,
  onManagePush,
  onSaved,
}: {
  pushOn: boolean;
  onManagePush: () => void;
  onSaved: () => void;
}) {
  const [data, setData] = useState<Preferences | null>(null);
  const [selected, setSelected] = useState<Preferences["preferences"] | null>(
    null,
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setError("");
    try {
      const next = await api<Preferences>("notification-preferences/");
      setData(next);
      setSelected(next.preferences);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  const dirty =
    !!data && JSON.stringify(selected) !== JSON.stringify(data.preferences);
  const toggle = (key: NotificationEvent, channel: "email" | "push") => {
    setSelected(
      (current) =>
        current && {
          ...current,
          [key]: { ...current[key], [channel]: !current[key][channel] },
        },
    );
  };
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const next = await api<Preferences>(
        "notification-preferences/",
        "PATCH",
        { preferences: selected },
      );
      setData(next);
      setSelected(next.preferences);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="settings-section">
      <div className="section-icon">
        <BellRing size={23} />
      </div>
      <h3>Miről szeretnél értesülni?</h3>
      <p>
        Az e-mailt és a push-t külön választhatod minden eseményhez. A csengőnél
        az alkalmazáson belüli értesítések mindig megmaradnak.
      </p>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {!data || !selected ? (
        error ? (
          <button className="btn secondary compact" onClick={load}>
            <RefreshCw size={16} />
            Újrapróbálás
          </button>
        ) : (
          <div className="loading">
            <LoaderCircle className="spin" size={20} />
            Beállítások betöltése…
          </div>
        )
      ) : (
        <>
          <div className="notification-email-address">
            <Mail size={16} />
            <span>
              E-mail-címed: <strong>{data.email}</strong>
            </span>
          </div>
          {!data.email_configured && (
            <div className="setup-note">
              Az e-mail-küldés beállítása még folyamatban van. A választásaidat
              már elmentheted; a küldés bekapcsolása után az új értesítésekre
              érvényesek.
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              save();
            }}
          >
            <table className="notification-preferences-table">
              <caption className="sr-only">
                Saját e-mail- és push-értesítéseim
              </caption>
              <thead>
                <tr>
                  <th scope="col">Esemény</th>
                  <th scope="col">E-mail</th>
                  <th scope="col">Push</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <tr key={event.key}>
                    <th scope="row">
                      <strong>{event.label}</strong>
                      <span>{event.description}</span>
                    </th>
                    {(["email", "push"] as const).map((channel) => (
                      <td key={channel}>
                        <label className="notification-choice">
                          <input
                            type="checkbox"
                            aria-label={`${event.label} — ${channel === "email" ? "e-mail" : "push"}`}
                            checked={selected[event.key][channel]}
                            disabled={busy}
                            onChange={() => toggle(event.key, channel)}
                          />
                        </label>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="form-hint">
              A mentés a következő értesítésekre vonatkozik. Saját műveleteidről
              nem küldünk külön értesítést.
            </p>
            <div className="notification-preferences-actions">
              <button
                type="submit"
                className="btn primary"
                disabled={busy || !dirty}
              >
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Check size={16} />
                )}
                Mentés
              </button>
              {dirty && (
                <span className="form-hint">Még nem mentett módosítások</span>
              )}
            </div>
          </form>
          <div className="notification-device-status">
            <BellRing size={18} />
            <div>
              <strong>
                {pushOn
                  ? "A push ezen az eszközön be van kapcsolva."
                  : "A push ezen az eszközön még nincs bekapcsolva."}
              </strong>
              <p>
                A kiválasztott push-értesítésekhez az eszköz engedélye is
                szükséges.
              </p>
              <button type="button" className="text-btn" onClick={onManagePush}>
                Eszköz push-beállításai
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
