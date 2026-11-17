import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { api } from "./api";

export const isRecoveryLink = () =>
  location.hash.startsWith("#reset=") || location.hash === "#forgot-password";

export function PasswordRecovery({ onBack }: { onBack: () => void }) {
  const [target] = useState(() => {
    const match = /^#reset=([A-Za-z0-9_-]{1,64})\/([A-Za-z0-9_-]{1,128})$/.exec(
      location.hash,
    );
    return match ? { uid: match[1], token: match[2] } : null;
  });
  const [confirm, setConfirm] = useState(location.hash.startsWith("#reset="));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <>
      <h2>{confirm ? "Új jelszó beállítása" : "Elfelejtetted a jelszavad?"}</h2>
      <p>
        {confirm
          ? "Adj meg egy legalább 10 karakteres, egyedi jelszót."
          : "Add meg a GURU-fiókod e-mail-címét, és küldünk egy visszaállító linket."}
      </p>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {message ? (
        <p role="status">{message}</p>
      ) : (
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setError("");
            if (confirm && !target) {
              setError("A visszaállító link hibás. Kérj új linket.");
              return;
            }
            if (confirm && password !== repeat) {
              setError("A két jelszó nem egyezik.");
              return;
            }
            setBusy(true);
            try {
              const result = await api<{ message: string }>(
                confirm ? "password-reset/confirm/" : "password-reset/",
                "POST",
                confirm ? { ...target, password } : { email },
              );
              setMessage(result.message);
              setPassword("");
              setRepeat("");
              history.replaceState(
                null,
                "",
                location.pathname + location.search,
              );
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {confirm ? (
            <>
              <label>
                Új jelszó
                <input
                  type="password"
                  name="new-password"
                  autoComplete="new-password"
                  minLength={10}
                  maxLength={1024}
                  required
                  autoFocus
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <label>
                Új jelszó még egyszer
                <input
                  type="password"
                  name="confirm-password"
                  autoComplete="new-password"
                  minLength={10}
                  maxLength={1024}
                  required
                  value={repeat}
                  onChange={(e) => setRepeat(e.target.value)}
                />
              </label>
            </>
          ) : (
            <label>
              E-mail-cím
              <input
                type="email"
                name="email"
                autoComplete="username"
                maxLength={254}
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          )}
          <button className="btn primary full" disabled={busy}>
            {busy && <LoaderCircle size={17} className="spin" />}
            {confirm ? "Új jelszó mentése" : "Visszaállító link küldése"}
          </button>
        </form>
      )}
      {confirm && !message && (
        <button
          type="button"
          className="btn full"
          disabled={busy}
          onClick={() => {
            setConfirm(false);
            setError("");
            history.replaceState(
              null,
              "",
              location.pathname + "#forgot-password",
            );
          }}
        >
          Új linket kérek
        </button>
      )}
      <button
        type="button"
        className="btn full"
        disabled={busy}
        onClick={onBack}
      >
        Vissza a belépéshez
      </button>
    </>
  );
}
