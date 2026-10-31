export const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file";
export type DriveConfig = {
  enabled: boolean;
  client_id: string;
  api_key: string;
  app_id: string;
};
export type DriveSelection = {
  file_id: string;
  resource_key: string;
  access_token: string;
};
type TokenResponse = {
  access_token?: string;
  expires_in?: number;
  scope?: string;
  error?: string;
};
type TokenClient = {
  requestAccessToken: (options: { prompt: string }) => void;
};
type PickerDocument = { id: string; resourceKey?: string };
type PickerResponse = { action: string; docs?: PickerDocument[] };
type Picker = { setVisible: (visible: boolean) => void; dispose: () => void };
type DocsView = {
  setEnableDrives: (value: boolean) => DocsView;
  setLabel: (label: string) => DocsView;
  setMode: (mode: string) => DocsView;
  setIncludeFolders: (value: boolean) => DocsView;
  setSelectFolderEnabled: (value: boolean) => DocsView;
};
type Builder = {
  addView: (view: DocsView) => Builder;
  setAppId: (value: string) => Builder;
  setDeveloperKey: (value: string) => Builder;
  setOAuthToken: (value: string) => Builder;
  setOrigin: (value: string) => Builder;
  setLocale: (value: string) => Builder;
  setTitle: (value: string) => Builder;
  setCallback: (callback: (result: PickerResponse) => void) => Builder;
  build: () => Picker;
};
type GoogleLibraries = {
  accounts?: {
    oauth2: {
      initTokenClient: (options: {
        client_id: string;
        scope: string;
        include_granted_scopes: boolean;
        callback: (response: TokenResponse) => void;
        error_callback: (error: { type: string }) => void;
      }) => TokenClient;
    };
  };
  picker?: {
    DocsView: new () => DocsView;
    DocsViewMode: { LIST: string };
    PickerBuilder: new () => Builder;
    Action: { PICKED: string; CANCEL: string };
  };
};
declare global {
  interface Window {
    google?: GoogleLibraries;
    gapi?: {
      load: (
        module: string,
        options: {
          callback: () => void;
          onerror: () => void;
          timeout: number;
          ontimeout: () => void;
        },
      ) => void;
    };
  }
}
let loading: Promise<void> | null = null;
function script(src: string, ready: () => boolean) {
  if (ready()) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const element = document.createElement("script");
    element.src = src;
    element.async = true;
    const timer = setTimeout(fail, 15000);
    function fail() {
      clearTimeout(timer);
      element.remove();
      reject(
        new Error(
          "A Google-fájlválasztó nem tölthető be. Ellenőrizd a kapcsolatot, majd próbáld újra.",
        ),
      );
    }
    element.onload = () => {
      clearTimeout(timer);
      if (ready()) resolve();
      else fail();
    };
    element.onerror = fail;
    document.head.append(element);
  });
}
export function loadDrivePicker(): Promise<void> {
  if (window.google?.picker && window.google?.accounts?.oauth2)
    return Promise.resolve();
  if (!loading)
    loading = Promise.all([
      script(
        "https://accounts.google.com/gsi/client",
        () => !!window.google?.accounts?.oauth2,
      ),
      script("https://apis.google.com/js/api.js", () => !!window.gapi),
    ])
      .then(
        () =>
          new Promise<void>((resolve, reject) => {
            const fail = () =>
              reject(
                new Error(
                  "A Google-fájlválasztó nem tölthető be. Próbáld újra.",
                ),
              );
            window.gapi!.load("picker", {
              callback: resolve,
              onerror: fail,
              timeout: 10000,
              ontimeout: fail,
            });
          }),
      )
      .catch((error) => {
        loading = null;
        throw error;
      });
  return loading;
}
export function driveTokenClient(
  clientId: string,
  callback: (response: TokenResponse) => void,
  onError: (type: string) => void,
) {
  return window.google!.accounts!.oauth2.initTokenClient({
    client_id: clientId,
    scope: DRIVE_SCOPE,
    include_granted_scopes: false,
    callback,
    error_callback: (error) => onError(error.type),
  });
}
export function showDrivePicker(
  config: DriveConfig,
  token: string,
  onPick: (selection: DriveSelection | null) => void,
): Picker {
  const api = window.google!.picker!;
  const view = new api.DocsView()
    .setMode(api.DocsViewMode.LIST)
    .setIncludeFolders(true)
    .setSelectFolderEnabled(false);
  const picker = new api.PickerBuilder()
    .addView(view)
    .addView(
      new api.DocsView()
        .setEnableDrives(true)
        .setMode(api.DocsViewMode.LIST)
        .setLabel("Megosztott meghajtók"),
    )
    .setAppId(config.app_id)
    .setDeveloperKey(config.api_key)
    .setOAuthToken(token)
    .setOrigin(location.origin)
    .setLocale("hu")
    .setTitle("Fájl csatolása a Google Drive-ból")
    .setCallback((result) => {
      if (result.action === api.Action.CANCEL) onPick(null);
      else if (result.action === api.Action.PICKED) {
        const file = result.docs?.[0];
        onPick(
          file
            ? {
                file_id: file.id,
                resource_key: file.resourceKey || "",
                access_token: token,
              }
            : null,
        );
      }
    })
    .build();
  picker.setVisible(true);
  return picker;
}
