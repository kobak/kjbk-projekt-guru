import { useState } from "react";
import { LoaderCircle, Mail } from "lucide-react";
import { api } from "./api";
import type { Member } from "./types";

export default function MemberEmailEditor({
  member,
  onCancel,
  onSaved,
}: {
  member: Member;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [email, setEmail] = useState(member.email);
  const [currentEmail] = useState(member.email);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  return (
    <form
      className="member-email-editor"
      aria-label={`${member.name} e-mail-címének módosítása`}
      onSubmit={async (event) => {
        event.preventDefault();
        if (saving) return;
        setSaving(true);
        setError("");
        try {
          await api(`members/${member.id}/`, "PATCH", {
            email,
            current_email: currentEmail,
          });
          await onSaved();
        } catch (error) {
          setError((error as Error).message);
        } finally {
          setSaving(false);
        }
      }}
    >
      <label htmlFor={`member-email-${member.id}`}>E-mail-cím</label>
      <div className="input-with-icon">
        <Mail size={16} />
        <input
          id={`member-email-${member.id}`}
          type="email"
          autoComplete="email"
          autoFocus
          maxLength={150}
          required
          disabled={saving}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <p className="form-hint">
        Ezzel a belépési cím is megváltozik. A jelszó, a feladatok és a
        beállítások megmaradnak.
      </p>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <div className="button-row">
        <button className="btn primary" disabled={saving}>
          {saving && <LoaderCircle size={15} className="spin" />}
          E-mail mentése
        </button>
        <button
          type="button"
          className="btn"
          disabled={saving}
          onClick={onCancel}
        >
          Mégse
        </button>
      </div>
    </form>
  );
}
