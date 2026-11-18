import { api } from "./api";

type AppleReply = { permission: string; token?: string; environment?: string };
type AppleBridge = {
  postMessage(message: { command: string; path?: string }): Promise<AppleReply>;
};
declare global {
  interface Window {
    webkit?: GuruWebKit;
  }
  interface GuruWebKit {
    messageHandlers?: {
      guruMac?: { postMessage(message: { command: string; path?: string }): void };
      guruMobile?: AppleBridge;
    };
  }
}
const bridge = () => window.webkit?.messageHandlers?.guruMobile;
export const isMobileApp = () => !!bridge();
export function mobileBrowser(path: string) {
  return bridge()?.postMessage({ command: "browser", path });
}

export type DeviceStatus = { configured: boolean; enabled: boolean; user_id: number };
export const mobileStatus = () => api<DeviceStatus>("apple/device/");
async function register(userID: number, prompt: boolean) {
  const reply = await bridge()?.postMessage({ command: prompt ? "enable" : "renew" });
  if (!reply?.token) {
    if (reply?.permission === "denied" || reply?.permission === "undetermined")
      await api("apple/device/", "DELETE", { user_id: userID });
    if (prompt) throw new Error("Engedélyezd a GURU értesítéseit a készülék Beállítások alkalmazásában.");
    return;
  }
  await api("apple/device/", "POST", { user_id: userID, token: reply.token, environment: reply.environment });
}

// Serialize foreground renewals with user changes so an older request can't undo a switch-off.
let pending: Promise<unknown> = Promise.resolve();
export function mobilePush(userID: number, action: "renew" | "toggle") {
  const run = pending.catch(() => {}).then(async () => {
    const status = await mobileStatus();
    if (status.user_id !== userID || !status.configured) return;
    if (action === "toggle" && status.enabled) {
      await api("apple/device/", "DELETE", { user_id: userID });
    } else if (action === "toggle" || status.enabled) {
      await register(userID, action === "toggle");
    }
    window.dispatchEvent(new Event("guru-mobile-push"));
  });
  pending = run;
  return run;
}
