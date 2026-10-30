import type { ListSort, Task } from "./types";

type SortableTask = Pick<
  Task,
  "id" | "due_date" | "due_time" | "priority" | "position" | "created_at"
>;
const priority = { urgent: 0, high: 1, normal: 2, low: 3 };
export function sortListTasks<T extends SortableTask>(
  tasks: T[],
  sort: ListSort,
  order: string[],
): T[] {
  const ranks = new Map(order.map((id, i) => [id, i]));
  const fallback = (a: T, b: T) =>
    a.position - b.position ||
    a.created_at.localeCompare(b.created_at) ||
    a.id.localeCompare(b.id);
  return [...tasks].sort((a, b) => {
    if (sort === "manual")
      return (
        (ranks.get(a.id) ?? Number.MAX_SAFE_INTEGER) -
          (ranks.get(b.id) ?? Number.MAX_SAFE_INTEGER) || fallback(a, b)
      );
    if (sort === "priority")
      return priority[a.priority] - priority[b.priority] || fallback(a, b);
    if (sort === "created")
      return (
        Date.parse(b.created_at) - Date.parse(a.created_at) || fallback(a, b)
      );
    if (!a.due_date && b.due_date) return 1;
    if (a.due_date && !b.due_date) return -1;
    return (
      (a.due_date || "").localeCompare(b.due_date || "") ||
      (a.due_time || "00:00").localeCompare(b.due_time || "00:00") ||
      fallback(a, b)
    );
  });
}
