export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T = Record<string, unknown>>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api/" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(form ? {} : { "Content-Type": "application/json" }),
      ...(method !== "GET" ? { "X-CSRFToken": csrf } : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      "A szerver válasza nem olvasható. Frissítsd az oldalt, és próbáld újra.",
      response.status,
    );
  }
  if (!response.ok)
    throw new ApiError(
      data.error || "A művelet nem sikerült.",
      response.status,
    );
  if (data.csrf) setCsrf(data.csrf);
  return data;
}
export const today = () =>
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Budapest",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const dayLabel = (date: string | null) =>
  !date
    ? "Nincs határidő"
    : date === today()
      ? "Ma"
      : new Intl.DateTimeFormat("hu-HU", {
          month: "short",
          day: "numeric",
        }).format(new Date(date + "T12:00:00"));
export const isOverdue = (task: {
  due_date: string | null;
  due_time: string | null;
  status: string;
}) =>
  task.status !== "done" &&
  !!task.due_date &&
  (task.due_date < today() ||
    (task.due_date === today() &&
      !!task.due_time &&
      task.due_time <
        new Intl.DateTimeFormat("sv-SE", {
          timeZone: "Europe/Budapest",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }).format(new Date())));
export const relative = (date: string) => {
  const m = Math.max(
    0,
    Math.floor((Date.now() - new Date(date).getTime()) / 60000),
  );
  return m < 1
    ? "épp most"
    : m < 60
      ? `${m} perce`
      : m < 1440
        ? `${Math.floor(m / 60)} órája`
        : new Intl.DateTimeFormat("hu-HU", {
            month: "short",
            day: "numeric",
          }).format(new Date(date));
};
