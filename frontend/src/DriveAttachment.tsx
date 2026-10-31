import { useEffect, useRef, useState } from "react";
import { HardDrive, LoaderCircle, RefreshCw } from "lucide-react";
import { api } from "./api";
import {
  DRIVE_SCOPE,
  driveTokenClient,
  loadDrivePicker,
  showDrivePicker,
} from "./drivePicker";
import type { DriveConfig, DriveSelection } from "./drivePicker";

export default function DriveAttachment({
  busy,
  onPick,
  onExternalDialog,
}: {
  busy: boolean;
  onPick: (selection: DriveSelection) => Promise<void>;
  onExternalDialog: (open: boolean) => void;
}) {
  const [ready, setReady] = useState(false),
    [configured, setConfigured] = useState<boolean | null>(null),
    [working, setWorking] = useState(false),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  const client = useRef<ReturnType<typeof driveTokenClient> | null>(null);
  const picker = useRef<ReturnType<typeof showDrivePicker> | null>(null);
  const callbacks = useRef({ onPick, onExternalDialog });
  callbacks.current = { onPick, onExternalDialog };
  useEffect(() => {
    let alive = true,
      handled = false;
    setReady(false);
    setError("");
    const finish = () => {
      if (!alive) return;
      setWorking(false);
      callbacks.current.onExternalDialog(false);
      picker.current?.dispose();
      picker.current = null;
    };
    const initialize = async () => {
      const config = await api<DriveConfig>("drive/config/");
      if (!alive) return;
      setConfigured(config.enabled);
      if (!config.enabled) return;
      await loadDrivePicker();
      if (!alive) return;
      client.current = driveTokenClient(
        config.client_id,
        (response) => {
          if (!alive) return;
          if (
            response.error ||
            !response.access_token ||
            !response.scope?.split(" ").includes(DRIVE_SCOPE)
          ) {
            setError(
              "A Google Drive-hozzáférés nem sikerült. Próbáld újra, és engedélyezd a kiválasztott fájlok használatát.",
            );
            finish();
            return;
          }
          handled = false;
          try {
            picker.current = showDrivePicker(
              config,
              response.access_token,
              async (selection) => {
                if (!alive || handled) return;
                handled = true;
                try {
                  if (selection) await callbacks.current.onPick(selection);
                } catch (exception) {
                  if (alive) setError((exception as Error).message);
                } finally {
                  finish();
                }
              },
            );
          } catch {
            setError(
              "A Google Drive-fájlválasztó nem nyílt meg. Próbáld újra.",
            );
            finish();
          }
        },
        (type) => {
          if (type !== "popup_closed")
            setError(
              "Engedélyezd a Google bejelentkezési ablakát a böngészőben, majd próbáld újra.",
            );
          finish();
        },
      );
      setReady(true);
    };
    initialize().catch((exception) => {
      if (alive) setError((exception as Error).message);
    });
    return () => {
      alive = false;
      client.current = null;
      picker.current?.dispose();
      picker.current = null;
      callbacks.current.onExternalDialog(false);
    };
  }, [attempt]);
  return (
    <section
      className="drive-attachment"
      aria-label="Google Drive-fájl csatolása"
    >
      <div>
        <HardDrive size={22} />
        <div>
          <strong>Google Drive</strong>
          <p>
            A kiválasztott fájl a Drive-on marad. A csapattagoknak ott is
            hozzáféréssel kell rendelkezniük.
          </p>
        </div>
      </div>
      <button
        type="button"
        className="btn secondary"
        disabled={!ready || busy || working}
        onClick={() => {
          setError("");
          setWorking(true);
          callbacks.current.onExternalDialog(true);
          // Keep this call synchronous with the click so browsers allow Google's popup.
          try {
            client.current!.requestAccessToken({ prompt: "select_account" });
          } catch {
            setError(
              "A Google bejelentkezési ablaka nem nyílt meg. Próbáld újra.",
            );
            setWorking(false);
            callbacks.current.onExternalDialog(false);
          }
        }}
      >
        {working || (configured && !ready && !error) ? (
          <LoaderCircle size={16} className="spin" />
        ) : (
          <HardDrive size={16} />
        )}
        Kiválasztás a Google Drive-ból
      </button>
      {configured === false && (
        <p className="form-hint">
          A Google Drive-kapcsolat beállítása még folyamatban van.
        </p>
      )}
      {error && (
        <div className="error-banner" role="alert">
          {error}
          {!ready && (
            <button
              type="button"
              className="text-btn"
              onClick={() => setAttempt((value) => value + 1)}
            >
              <RefreshCw size={14} />
              Újrapróbálás
            </button>
          )}
        </div>
      )}
    </section>
  );
}
