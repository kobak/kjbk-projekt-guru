import { useEffect, useRef, useState } from "react";
import {
  Check,
  LoaderCircle,
  Monitor,
  Moon,
  Sun,
  SlidersHorizontal,
} from "lucide-react";
import { chooseAppearance, chooseTheme, useAppearance } from "./theme";
import type { Appearance, ListSort, ThemeMode } from "./types";

export const themeOptions = [
  { value: "light" as ThemeMode, label: "Világos", Icon: Sun },
  { value: "dark" as ThemeMode, label: "Sötét", Icon: Moon },
  { value: "system" as ThemeMode, label: "Rendszer szerint", Icon: Monitor },
];

export default function ThemeSwitcher({
  settings = false,
  onSettings,
}: {
  settings?: boolean;
  onSettings?: () => void;
}) {
  const appearance = useAppearance();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const current = themeOptions.find(
    (option) => option.value === appearance.mode,
  )!;
  useEffect(() => {
    if (!open) return;
    const pointer = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keyboard, true);
    return () => {
      document.removeEventListener("pointerdown", pointer);
      document.removeEventListener("keydown", keyboard, true);
    };
  }, [open]);
  const options = themeOptions.map(({ value, label, Icon }) => (
    <button
      key={value}
      type="button"
      className={"theme-option " + (appearance.mode === value ? "active" : "")}
      aria-pressed={appearance.mode === value}
      disabled={appearance.saving}
      onClick={() => {
        chooseTheme(value);
        setOpen(false);
        trigger.current?.focus();
      }}
    >
      <Icon size={18} />
      <span>{label}</span>
      {appearance.mode === value && <Check size={15} />}
    </button>
  ));
  if (settings)
    return (
      <section className="settings-section">
        <div className="section-icon">
          <current.Icon size={22} />
        </div>
        <h3>Megjelenés</h3>
        <p>
          Válassz világos vagy sötét felületet, vagy kövesd a készülék
          beállítását. A választás a saját fiókodhoz mentődik.
        </p>
        <div className="theme-choices" role="group" aria-label="Megjelenés">
          {options}
        </div>
        <div className="form-grid appearance-grid">
          <label>
            Betűméret
            <select
              value={appearance.font_size}
              disabled={appearance.saving}
              onChange={(e) =>
                chooseAppearance({
                  font_size: e.target.value as Appearance["font_size"],
                })
              }
            >
              <option value="normal">Normál</option>
              <option value="large">Nagy</option>
            </select>
          </label>
          <label>
            Sűrűség
            <select
              value={appearance.density}
              disabled={appearance.saving}
              onChange={(e) =>
                chooseAppearance({
                  density: e.target.value as Appearance["density"],
                })
              }
            >
              <option value="compact">Kompakt</option>
              <option value="spacious">Tágas</option>
            </select>
          </label>
          <label>
            Alapértelmezett feladatnézet
            <select
              value={appearance.default_view}
              disabled={appearance.saving}
              onChange={(e) =>
                chooseAppearance({
                  default_view: e.target.value as Appearance["default_view"],
                })
              }
            >
              <option value="list">Lista</option>
              <option value="board">Kanban (Tábla)</option>
            </select>
          </label>
          <label>
            Lista rendezése
            <select
              value={appearance.list_sort}
              disabled={appearance.saving}
              onChange={(e) =>
                chooseAppearance({ list_sort: e.target.value as ListSort })
              }
            >
              <option value="due">Határidő szerint</option>
              <option value="priority">Prioritás szerint</option>
              <option value="created">Legújabb elöl</option>
              <option value="manual">Saját kézi sorrend</option>
            </select>
          </label>
        </div>
        <label className="appearance-checkbox">
          <input
            type="checkbox"
            checked={appearance.show_completed}
            disabled={appearance.saving}
            onChange={(e) =>
              chooseAppearance({ show_completed: e.target.checked })
            }
          />
          Kész feladatok is a listában
        </label>
        <p className="form-hint">
          A betűméret és a sűrűség az asztali felületet módosítja. Minden
          választás automatikusan a fiókodhoz mentődik.
        </p>
        {appearance.saving && (
          <p className="form-hint" role="status">
            <LoaderCircle size={13} className="spin" />
            Mentés…
          </p>
        )}
        {appearance.error && (
          <div className="error-banner" role="alert">
            {appearance.error}
          </div>
        )}
      </section>
    );
  return (
    <div className="theme-switcher" ref={ref}>
      <button
        type="button"
        className="icon-btn"
        ref={trigger}
        aria-label={`Megjelenés: ${current.label}`}
        title={`Megjelenés: ${current.label}`}
        aria-expanded={open}
        aria-controls="theme-menu"
        onClick={() => setOpen(!open)}
      >
        {appearance.saving ? (
          <LoaderCircle size={18} className="spin" />
        ) : (
          <current.Icon size={18} />
        )}
      </button>
      {open && (
        <div
          id="theme-menu"
          className="theme-menu"
          role="group"
          aria-label="Megjelenés kiválasztása"
        >
          {options}
          {onSettings && (
            <button
              type="button"
              className="theme-option"
              onClick={() => {
                setOpen(false);
                onSettings();
              }}
            >
              <SlidersHorizontal size={18} />
              <span>Betűméret és nézet</span>
            </button>
          )}
        </div>
      )}
      {appearance.error && (
        <p className="theme-error" role="alert">
          {appearance.error}
        </p>
      )}
    </div>
  );
}
