type MacState = { notificationsEnabled: boolean };
declare global {
  interface Window {
    guruMac?: MacState;
    webkit?: {
      messageHandlers?: {
        guruMac?: {
          postMessage: (message: { command: string; path?: string }) => void;
        };
      };
    };
  }
}
export const isMacApp = () =>
  !!window.guruMac && !!window.webkit?.messageHandlers?.guruMac;
export const macNotificationsEnabled = () =>
  !!window.guruMac?.notificationsEnabled;
export function macCommand(
  command: "notifications" | "browser" | "settings",
  path?: string,
) {
  window.webkit?.messageHandlers?.guruMac?.postMessage({ command, path });
}
