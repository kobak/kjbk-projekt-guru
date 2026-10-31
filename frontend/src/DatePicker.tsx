import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { today } from "./api";
import { dateKey, monthDays, shiftMonth } from "./calendarDates";

const weekdays = [
  ["H", "hétfő"],
  ["K", "kedd"],
  ["Sze", "szerda"],
  ["Cs", "csütörtök"],
  ["P", "péntek"],
  ["Szo", "szombat"],
  ["V", "vasárnap"],
];
const label = (date: Date) =>
  new Intl.DateTimeFormat("hu-HU", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);

export default function DatePicker({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const focusDay = useRef(false);
  const [open, setOpen] = useState(false);
  const [popupTop, setPopupTop] = useState<number>();
  const [focused, setFocused] = useState(
    () => new Date((value || today()) + "T12:00:00"),
  );
  const days = monthDays(focused);
  const selected = value ? new Date(value + "T12:00:00") : null;
  const close = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  };
  const choose = (next: string) => {
    onChange(next);
    close();
  };
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  useLayoutEffect(() => {
    if (open && focusDay.current) {
      root.current
        ?.querySelector<HTMLButtonElement>(`[data-date="${dateKey(focused)}"]`)
        ?.focus({ preventScroll: true });
      focusDay.current = false;
    }
    if (open && root.current && trigger.current && popup.current) {
      const bounds = root.current.closest(".modal")?.getBoundingClientRect();
      const rootTop = root.current.getBoundingClientRect().top;
      const headerHeight =
        root.current
          .closest(".modal")
          ?.querySelector(".modal-heading")
          ?.getBoundingClientRect().height || 0;
      const top = Math.max(
        (bounds?.top || 0) + headerHeight + 8,
        Math.min(
          trigger.current.getBoundingClientRect().bottom + 6,
          Math.min(innerHeight, bounds?.bottom || innerHeight) -
            popup.current.getBoundingClientRect().height -
            12,
        ),
      );
      setPopupTop(top - rootTop);
    }
  }, [open, focused]);
  const move = (date: Date) => {
    if (date.getFullYear() < 1 || date.getFullYear() > 9999) return;
    focusDay.current = true;
    setFocused(date);
  };
  return (
    <div
      className="date-field"
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node))
          setOpen(false);
      }}
    >
      <label htmlFor={id}>Határidő</label>
      <button
        id={id}
        ref={trigger}
        type="button"
        className="date-trigger"
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${id}-calendar` : undefined}
        aria-label={`Határidő: ${selected ? label(selected) : "nincs megadva"}`}
        onClick={() => {
          if (open) close();
          else {
            setFocused(new Date((value || today()) + "T12:00:00"));
            focusDay.current = true;
            setPopupTop(undefined);
            setOpen(true);
          }
        }}
      >
        <span>
          {selected
            ? new Intl.DateTimeFormat("hu-HU").format(selected)
            : "Válassz dátumot"}
        </span>
        <CalendarDays size={17} />
      </button>
      {open && (
        <div
          id={`${id}-calendar`}
          ref={popup}
          style={{ top: popupTop }}
          className="date-popover"
          role="dialog"
          aria-label="Határidő kiválasztása"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              close();
            }
          }}
        >
          <div className="date-navigation">
            <button
              type="button"
              className="icon-btn"
              aria-label="Előző hónap"
              onClick={() => move(shiftMonth(focused, -1))}
            >
              <ChevronLeft size={18} />
            </button>
            <strong id={`${id}-month`} aria-live="polite">
              {new Intl.DateTimeFormat("hu-HU", {
                year: "numeric",
                month: "long",
              }).format(focused)}
            </strong>
            <button
              type="button"
              className="icon-btn"
              aria-label="Következő hónap"
              onClick={() => move(shiftMonth(focused, 1))}
            >
              <ChevronRight size={18} />
            </button>
          </div>
          <table
            role="grid"
            aria-labelledby={`${id}-month`}
            className="date-grid"
          >
            <thead>
              <tr>
                {weekdays.map(([short, full]) => (
                  <th key={full} scope="col" abbr={full}>
                    {short}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 6 }, (_, week) => (
                <tr key={week}>
                  {days.slice(week * 7, week * 7 + 7).map((day) => {
                    const key = dateKey(day);
                    return (
                      <td key={key} aria-selected={key === value}>
                        <button
                          type="button"
                          data-date={key}
                          aria-label={label(day)}
                          aria-current={key === today() ? "date" : undefined}
                          tabIndex={key === dateKey(focused) ? 0 : -1}
                          className={
                            (day.getMonth() !== focused.getMonth()
                              ? "outside "
                              : "") + (key === value ? "selected" : "")
                          }
                          onClick={() => choose(key)}
                          onKeyDown={(event) => {
                            let next = new Date(day);
                            const offsets: Record<string, number> = {
                              ArrowLeft: -1,
                              ArrowRight: 1,
                              ArrowUp: -7,
                              ArrowDown: 7,
                            };
                            if (event.key in offsets)
                              next.setDate(next.getDate() + offsets[event.key]);
                            else if (event.key === "Home")
                              next.setDate(
                                next.getDate() - ((next.getDay() + 6) % 7),
                              );
                            else if (event.key === "End")
                              next.setDate(
                                next.getDate() + 6 - ((next.getDay() + 6) % 7),
                              );
                            else if (
                              event.key === "PageUp" ||
                              event.key === "PageDown"
                            )
                              next = shiftMonth(
                                next,
                                (event.key === "PageUp" ? -1 : 1) *
                                  (event.shiftKey ? 12 : 1),
                              );
                            else return;
                            event.preventDefault();
                            move(next);
                          }}
                        >
                          {day.getDate()}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="date-actions">
            <button
              type="button"
              className="text-btn"
              onClick={() => choose(today())}
            >
              Ma
            </button>
            <button
              type="button"
              className="text-btn"
              onClick={() => choose("")}
            >
              Határidő törlése
            </button>
            <button type="button" className="text-btn" onClick={() => close()}>
              Bezárás
            </button>
          </div>
          <p className="sr-only">
            Mozgás a nyilakkal, hónapváltás Page Up és Page Down, évváltás Shift
            billentyűvel. Kiválasztás Enterrel, bezárás Escape-pel.
          </p>
        </div>
      )}
    </div>
  );
}
