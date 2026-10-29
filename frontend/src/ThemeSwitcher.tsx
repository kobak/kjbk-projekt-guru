import { useEffect, useRef, useState } from "react";
import { Check, LoaderCircle, Monitor, Moon, Sun } from "lucide-react";
import { chooseTheme, useAppearance } from "./theme";
import type { ThemeMode } from "./types";

export const themeOptions = [
  { value: "light" as ThemeMode, label: "Világos", Icon: Sun },
  { value: "dark" as ThemeMode, label: "Sötét", Icon: Moon },
  { value: "system" as ThemeMode, label: "Rendszer szerint", Icon: Monitor },
];

export default function ThemeSwitcher({
  settings = false,
}: {
  settings?: boolean;
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
