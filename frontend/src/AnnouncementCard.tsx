import { ArrowUpRight, LoaderCircle, Megaphone, X } from "lucide-react";
import type { Announcement } from "./types";

export default function AnnouncementCard({
  announcement,
  onDismiss,
  busy = false,
  preview = false,
}: {
  announcement: Pick<
    Announcement,
    "title" | "body" | "link_label" | "link_url"
  >;
  onDismiss?: () => void;
  busy?: boolean;
  preview?: boolean;
}) {
  const linkContent = (
    <>
      {announcement.link_label}
      <ArrowUpRight size={14} aria-hidden="true" />
    </>
  );
  return (
    <section
      className="announcement-card"
      aria-label={preview ? "Hír előnézete" : "Kiemelt hír"}
    >
      <div className="announcement-symbol" aria-hidden="true">
        <Megaphone size={19} />
      </div>
      <div className="announcement-content">
        <span className="announcement-eyebrow">GURU hírek</span>
        <h2>{announcement.title}</h2>
        {announcement.body && (
          <p className="announcement-body">{announcement.body}</p>
        )}
        {announcement.link_url &&
          announcement.link_label &&
          (preview ? (
            <span className="announcement-link">{linkContent}</span>
          ) : (
            <a
              className="announcement-link"
              href={announcement.link_url}
              target={
                announcement.link_url.startsWith("/") ? undefined : "_blank"
              }
              rel={
                announcement.link_url.startsWith("/")
                  ? undefined
                  : "noopener noreferrer"
              }
            >
              {linkContent}
            </a>
          ))}
      </div>
      {onDismiss && (
        <button
          className="icon-btn announcement-dismiss"
          type="button"
          disabled={busy}
          aria-label="Hír elrejtése a saját fiókomban"
          title="Elrejtés a saját fiókomban"
          onClick={onDismiss}
        >
          {busy ? <LoaderCircle size={15} className="spin" /> : <X size={15} />}
        </button>
      )}
    </section>
  );
}
