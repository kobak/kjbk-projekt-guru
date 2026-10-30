import { useSyncExternalStore } from "react";
import { api } from "./api";
import type { Appearance, ThemeMode } from "./types";

type Settings = Omit<Appearance, "updated_at">;
declare global {
  interface Window {
    GuruAppearance: {
      apply: (mode: ThemeMode, cache?: boolean) => void;
      applyLayout?: (
        font: Settings["font_size"],
        density: Settings["density"],
        cache?: boolean,
      ) => void;
    };
  }
}
const defaults: Settings = {
  theme: "system",
  default_view: "list",
  show_completed: false,
  list_sort: "due",
  font_size: "normal",
  density: "compact",
};
function currentMode(): ThemeMode {
  const value = document.documentElement.dataset.themeMode;
  return value === "light" || value === "dark" ? value : "system";
}
let snapshot = {
  ...defaults,
  theme: currentMode(),
  mode: currentMode(),
  resolved:
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  font_size:
    document.documentElement.dataset.fontSize === "large"
      ? ("large" as const)
      : ("normal" as const),
  density:
    document.documentElement.dataset.density === "spacious"
      ? ("spacious" as const)
      : ("compact" as const),
  saving: false,
  error: "",
};
let accountId: number | null = null;
let revision = 0;
const listeners = new Set<() => void>();
function emit() {
  snapshot = {
    ...snapshot,
    theme: currentMode(),
    mode: currentMode(),
    resolved:
      document.documentElement.dataset.theme === "dark" ? "dark" : "light",
    font_size:
      document.documentElement.dataset.fontSize === "large"
        ? "large"
        : "normal",
    density:
      document.documentElement.dataset.density === "spacious"
        ? "spacious"
        : "compact",
  };
  listeners.forEach((listener) => listener());
}
function apply() {
  const { theme, font_size, density } = snapshot;
  window.GuruAppearance.apply(theme);
  if (window.GuruAppearance.applyLayout)
    window.GuruAppearance.applyLayout(font_size, density);
  else {
    document.documentElement.dataset.fontSize = font_size;
    document.documentElement.dataset.density = density;
    emit();
  }
}
window.addEventListener("guru-theme-change", emit);

export function syncAppearance(userId: number | null, appearance: Appearance) {
  if (accountId !== userId) {
    accountId = userId;
    revision = 0;
    snapshot = { ...snapshot, ...defaults, saving: false, error: "" };
  }
  if (!userId || snapshot.saving) return;
  const nextRevision = appearance.updated_at
    ? Date.parse(appearance.updated_at)
    : 0;
  if (nextRevision < revision) return;
  revision = nextRevision;
  snapshot = { ...snapshot, ...defaults, ...appearance };
  apply();
}

export function resetAppearance() {
  accountId = null;
  revision = 0;
  snapshot = { ...snapshot, ...defaults, saving: false, error: "" };
  apply();
}

export async function chooseAppearance(changes: Partial<Settings>) {
  if (snapshot.saving) return;
  const previous = snapshot;
  const savingAccount = accountId;
  snapshot = {
    ...snapshot,
    ...changes,
    saving: savingAccount !== null,
    error: "",
  };
  apply();
  if (savingAccount === null) return;
  try {
    const saved = await api<Appearance>("appearance/", "PATCH", changes);
    if (accountId !== savingAccount) return;
    revision = saved.updated_at ? Date.parse(saved.updated_at) : 0;
    snapshot = { ...snapshot, ...saved, saving: false };
    apply();
  } catch (error) {
    if (accountId !== savingAccount) return;
    snapshot = { ...previous, saving: false, error: (error as Error).message };
    apply();
  }
}
export const chooseTheme = (theme: ThemeMode) => chooseAppearance({ theme });

export function useAppearance() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => snapshot,
  );
}
