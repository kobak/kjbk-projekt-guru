import { useSyncExternalStore } from "react";
import { api } from "./api";
import type { Appearance, ThemeMode } from "./types";

declare global {
  interface Window {
    GuruAppearance: { apply: (mode: ThemeMode, cache?: boolean) => void };
  }
}

const modes: ThemeMode[] = ["system", "light", "dark"];
function currentMode(): ThemeMode {
  const value = document.documentElement.dataset.themeMode as ThemeMode;
  return modes.includes(value) ? value : "system";
}
let snapshot = {
  mode: currentMode(),
  resolved:
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  saving: false,
  error: "",
};
let accountId: number | null = null;
let revision = 0;
const listeners = new Set<() => void>();
function emit() {
  snapshot = {
    ...snapshot,
    mode: currentMode(),
    resolved:
      document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  };
  listeners.forEach((listener) => listener());
}
window.addEventListener("guru-theme-change", emit);

export function syncAppearance(userId: number | null, appearance: Appearance) {
  if (accountId !== userId) {
    accountId = userId;
    revision = 0;
    snapshot = { ...snapshot, saving: false, error: "" };
  }
  if (!userId || snapshot.saving) return;
  const nextRevision = appearance.updated_at
    ? Date.parse(appearance.updated_at)
    : 0;
  if (nextRevision < revision) return;
  revision = nextRevision;
  window.GuruAppearance.apply(appearance.theme);
}

export function resetAppearance() {
  accountId = null;
  revision = 0;
  snapshot = { ...snapshot, saving: false, error: "" };
  window.GuruAppearance.apply("system");
}

export async function chooseTheme(mode: ThemeMode) {
  if (snapshot.saving || !modes.includes(mode)) return;
  const previous = snapshot.mode;
  const savingAccount = accountId;
  snapshot = { ...snapshot, saving: savingAccount !== null, error: "" };
  window.GuruAppearance.apply(mode);
  if (savingAccount === null) return;
  try {
    const saved = await api<Appearance>("appearance/", "PATCH", {
      theme: mode,
    });
    if (accountId !== savingAccount) return;
    revision = saved.updated_at ? Date.parse(saved.updated_at) : 0;
    snapshot = { ...snapshot, saving: false };
    window.GuruAppearance.apply(saved.theme);
  } catch (error) {
    if (accountId !== savingAccount) return;
    snapshot = { ...snapshot, saving: false, error: (error as Error).message };
    window.GuruAppearance.apply(previous);
  }
}

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
