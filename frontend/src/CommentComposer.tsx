import { useId, useLayoutEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import type { Member } from "./types";
import { Avatar } from "./ui";
import {
  editMentions,
  mentionName,
  mentionQuery,
  searchable,
} from "./mentions";
import type { Mention } from "./mentions";

export default function CommentComposer({
  members,
  body,
  mentions,
  onChange,
  onSubmit,
  busy,
}: {
  members: Member[];
  body: string;
  mentions: Mention[];
  onChange: (body: string, mentions: Mention[]) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const pendingSelection = useRef<number | null>(null);
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const query = dismissed ? null : mentionQuery(body, caret, mentions);
  const choices = query
    ? members
        .filter(
          (user) =>
            user.active &&
            searchable(`${user.name} ${user.email}`).includes(
              searchable(query.search),
            ),
        )
        .slice(0, 10)
    : [];
  const index = Math.min(active, Math.max(0, choices.length - 1));
  const selectedUsers = members.filter((user) =>
    mentions.some((mention) => mention.user_id === user.id),
  );
  useLayoutEffect(() => {
    const position = pendingSelection.current;
    if (position !== null) {
      pendingSelection.current = null;
      input.current?.focus();
      input.current?.setSelectionRange(position, position);
    }
  }, [body, mentions]);
  const pick = (user: Member) => {
    if (!query) return;
    const token = "@" + mentionName(user.name);
    const next =
      body.slice(0, query.start) + token + " " + body.slice(query.end);
    if (next.length > 10000) return;
    const kept = editMentions(body, next, mentions);
    const position = query.start + token.length + 1;
    pendingSelection.current = position;
    onChange(
      next,
      [
        ...kept,
        {
          user_id: user.id,
          start: query.start,
          end: query.start + token.length,
        },
      ].sort((a, b) => a.start - b.start),
    );
    setDismissed(true);
    setCaret(position);
  };
  return (
    <form
      className="comment-compose"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="mention-editor">
        <textarea
          ref={input}
          aria-label="Hozzászólás"
          value={body}
          disabled={busy}
          placeholder="Írj hozzászólást… @ jellel megemlíthetsz valakit"
          aria-describedby={`${id}-help`}
          aria-autocomplete="list"
          aria-controls={query ? `${id}-members` : undefined}
          aria-activedescendant={
            choices.length ? `${id}-member-${choices[index].id}` : undefined
          }
          required
          maxLength={10000}
          rows={3}
          onChange={(event) => {
            const next = event.target.value;
            onChange(next, editMentions(body, next, mentions));
            setCaret(event.target.selectionStart);
            setActive(0);
            setDismissed(false);
          }}
          onSelect={(event) => setCaret(event.currentTarget.selectionStart)}
          onBlur={() => setDismissed(true)}
          onKeyDown={(event) => {
            if (!query || event.nativeEvent.isComposing) return;
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              setDismissed(true);
            } else if (
              choices.length &&
              !(event.key === "Tab" && event.shiftKey) &&
              ["ArrowDown", "ArrowUp", "Enter", "Tab"].includes(event.key)
            ) {
              event.preventDefault();
              if (event.key === "Enter" || event.key === "Tab")
                pick(choices[index]);
              else
                setActive(
                  (index +
                    (event.key === "ArrowDown" ? 1 : -1) +
                    choices.length) %
                    choices.length,
                );
            }
          }}
        />
        {query && (
          <div
            id={`${id}-members`}
            role="listbox"
            aria-label="Csapattagok említéshez"
            className="mention-choices"
          >
            {choices.length ? (
              choices.map((user, i) => (
                <button
                  id={`${id}-member-${user.id}`}
                  key={user.id}
                  type="button"
                  role="option"
                  aria-selected={i === index}
                  tabIndex={-1}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(user)}
                >
                  <Avatar user={user} />
                  <span>
                    <strong>{user.name}</strong>
                    <small>{user.email}</small>
                  </span>
                </button>
              ))
            ) : (
              <p role="status">Nincs ilyen csapattag.</p>
            )}
          </div>
        )}
      </div>
      {selectedUsers.length > 0 && (
        <div className="selected-mentions" aria-label="Kiválasztott említések">
          <span>Említések:</span>
          {selectedUsers.map((user) => (
            <span key={user.id} title={user.email}>
              @{user.name}
            </span>
          ))}
        </div>
      )}
      <div className="comment-compose-footer">
        <span id={`${id}-help`}>@ után válassz a csapattagok közül.</span>
        <button className="btn primary" disabled={busy || !body.trim()}>
          <Send size={16} />
          Küldés
        </button>
      </div>
    </form>
  );
}
