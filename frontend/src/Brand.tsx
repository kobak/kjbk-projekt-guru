const legacyProjectColors: Record<string, string> = {
  "#557c69": "#462773",
  "#638773": "#462773",
  "#a28bb2": "#e52053",
  "#c69a60": "#ee5a1e",
  "#668fa8": "#9a97a3",
  "#c27d78": "#1fa463",
  "#7c86b6": "#f5a623",
};

export function brandProjectColor(color: string) {
  return legacyProjectColors[color.toLowerCase()] || color;
}

export function projectDisplayColor(color?: string) {
  return color
    ? `color-mix(in srgb, ${color}, white var(--project-color-lightness))`
    : undefined;
}

export default function Brand({ full = false }: { full?: boolean }) {
  return (
    <span
      className={"brand-lockup" + (full ? " brand-lockup-full" : "")}
      role="img"
      aria-label="kjbk projekt guru"
    >
      <img
        className="brand-logo-light"
        src={
          full
            ? "/static/brand/kjbk-infinity.png"
            : "/static/brand/infinity-mark.png"
        }
        alt=""
        width={full ? 140 : 32}
        height={full ? 89 : 16}
      />
      <img
        className="brand-logo-dark"
        src={
          full
            ? "/static/brand/kjbk-infinity-negative.png"
            : "/static/brand/infinity-mark-negative.png"
        }
        alt=""
        width={full ? 140 : 32}
        height={full ? 89 : 16}
      />
      <span className="brand-name" aria-hidden="true">
        {!full && <strong>kjbk</strong>}
        <span>projekt guru</span>
      </span>
    </span>
  );
}
