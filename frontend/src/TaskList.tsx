import { useEffect, useRef, useState } from "react";
import { CalendarDays, Flag, GripVertical, Search } from "lucide-react";
import { dayLabel, isOverdue } from "./api";
import { projectDisplayColor } from "./Brand";
import { Avatar, priorities, StatusMark, statuses } from "./ui";
import type { Bootstrap, Task } from "./types";

type Drop = { id: string; placement: "before" | "after" };
export default function TaskList({
  tasks,
  data,
  manual,
  readOnly,
  onOpen,
  onToggle,
  onProject,
  onMove,
}: {
  tasks: Task[];
  data: Bootstrap;
  manual: boolean;
  readOnly: boolean;
  onOpen: (task: Task) => void;
  onToggle: (task: Task) => void;
  onProject: (id: string) => void;
  onMove: (
    id: string,
    target: string,
    placement: "before" | "after",
  ) => Promise<void>;
}) {
  const [moving, setMoving] = useState(false);
  const [dragged, setDragged] = useState<string | null>(null);
  const [drop, setDrop] = useState<Drop | null>(null);
  const [message, setMessage] = useState("");
  const table = useRef<HTMLDivElement>(null);
  const pointer = useRef<{
    id: string;
    startY: number;
    x: number;
    y: number;
    active: boolean;
  } | null>(null);
  const target = useRef<Drop | null>(null);
  const frame = useRef(0);
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  useEffect(() => setMessage(""), [manual]);
  const clearDrag = () => {
    pointer.current = null;
    target.current = null;
    cancelAnimationFrame(frame.current);
    setDragged(null);
    setDrop(null);
  };
  const locate = () => {
    const p = pointer.current;
    if (!p?.active) return;
    const row = document
      .elementsFromPoint(p.x, p.y)
      .map((element) => element.closest<HTMLElement>("[data-list-task]"))
      .find((element) => element && table.current?.contains(element));
    const id = row?.dataset.listTask;
    const next =
      row && id && id !== p.id
        ? {
            id,
            placement:
              p.y <
              row.getBoundingClientRect().top +
                row.getBoundingClientRect().height / 2
                ? ("before" as const)
                : ("after" as const),
          }
        : null;
    if (
      next?.id !== target.current?.id ||
      next?.placement !== target.current?.placement
    ) {
      target.current = next;
      setDrop(next);
    }
  };
  const scroll = () => {
    const p = pointer.current;
    if (!p?.active) return;
    const delta = p.y < 90 ? -12 : p.y > window.innerHeight - 90 ? 12 : 0;
    if (delta) {
      window.scrollBy(0, delta);
      locate();
    }
    frame.current = requestAnimationFrame(scroll);
  };
  const move = async (id: string, destination: Drop) => {
    if (moving || id === destination.id) return;
    setMoving(true);
    setMessage("");
    try {
      await onMove(id, destination.id, destination.placement);
      setMessage("A személyes sorrended elmentve.");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setMoving(false);
    }
  };
  const canMove = manual && !readOnly && !moving;
  return (
    <div className="task-list-wrapper">
      {manual && (
        <p className="list-order-hint">
          Saját sorrend: húzd a sor elején lévő fogantyút. Billentyűzettel a
          fel/le nyilakat is használhatod.
        </p>
      )}
      <div
        className={message ? "list-order-message" : "sr-only"}
        role="status"
        aria-live="polite"
      >
        {message}
      </div>
      <div
        className={"task-table " + (manual ? "manual-list" : "")}
        ref={table}
        aria-busy={moving}
      >
        <div className="table-header">
          <span>Feladat</span>
          <span>Projekt</span>
          <span>Határidő</span>
          <span>Prioritás</span>
          <span>Felelős</span>
        </div>
        {tasks.length ? (
          tasks.map((task, index) => (
            <div
              key={task.id}
              data-list-task={task.id}
              className={
                "table-row " +
                (task.status === "done" ? "done-row " : "") +
                (dragged === task.id ? "list-dragging " : "") +
                (drop?.id === task.id ? "list-drop-" + drop.placement : "")
              }
            >
              <div>
                {manual && (
                  <button
                    type="button"
                    className="list-drag-handle"
                    disabled={readOnly}
                    aria-disabled={!canMove}
                    aria-label={`Átrendezés: ${task.title}`}
                    title="Húzással vagy a fel/le nyilakkal rendezhető"
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        clearDrag();
                        return;
                      }
                      if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
                      event.preventDefault();
                      if (!canMove) return;
                      const previous = event.key === "ArrowUp";
                      const neighbor = tasks[index + (previous ? -1 : 1)];
                      if (neighbor)
                        move(task.id, {
                          id: neighbor.id,
                          placement: previous ? "before" : "after",
                        });
                    }}
                    onPointerDown={(event) => {
                      if (!canMove || event.button !== 0) return;
                      event.preventDefault();
                      event.currentTarget.focus();
                      event.currentTarget.setPointerCapture(event.pointerId);
                      pointer.current = {
                        id: task.id,
                        startY: event.clientY,
                        x: event.clientX,
                        y: event.clientY,
                        active: false,
                      };
                    }}
                    onPointerMove={(event) => {
                      const p = pointer.current;
                      if (!p) return;
                      p.x = event.clientX;
                      p.y = event.clientY;
                      if (!p.active && Math.abs(p.y - p.startY) > 5) {
                        p.active = true;
                        setDragged(p.id);
                        frame.current = requestAnimationFrame(scroll);
                      }
                      locate();
                    }}
                    onPointerUp={(event) => {
                      const p = pointer.current,
                        destination = target.current;
                      if (
                        event.currentTarget.hasPointerCapture(event.pointerId)
                      )
                        event.currentTarget.releasePointerCapture(
                          event.pointerId,
                        );
                      clearDrag();
                      if (p?.active && destination) move(p.id, destination);
                    }}
                    onPointerCancel={clearDrag}
                  >
                    <GripVertical size={16} />
                  </button>
                )}
                <StatusMark
                  value={task.status}
                  onClick={() => !readOnly && onToggle(task)}
                />
                <button className="table-title" onClick={() => onOpen(task)}>
                  {task.title}
                  <small>
                    {
                      statuses.find((status) => status.key === task.status)
                        ?.label
                    }
                  </small>
                </button>
              </div>
              <button
                className="table-project"
                onClick={() => onProject(task.project_id)}
              >
                <i
                  style={{
                    background: projectDisplayColor(
                      data.projects.find(
                        (project) => project.id === task.project_id,
                      )?.color,
                    ),
                  }}
                />
                {
                  data.projects.find(
                    (project) => project.id === task.project_id,
                  )?.name
                }
              </button>
              <span
                className={"table-date " + (isOverdue(task) ? "overdue" : "")}
              >
                <CalendarDays size={13} />
                {dayLabel(task.due_date)}
                {task.due_time && <small>{task.due_time}</small>}
              </span>
              <span className={"priority-text " + task.priority}>
                <Flag size={13} />
                {priorities[task.priority]}
              </span>
              <div className="table-assignee">
                <Avatar
                  user={data.members.find(
                    (user) => user.id === task.assignee_id,
                  )}
                  size="small"
                />
                <span>
                  {data.members.find((user) => user.id === task.assignee_id)
                    ?.name || "Nincs felelős"}
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-small">
            <Search size={28} />
            <h3>Még nincs itt feladat.</h3>
            <p>Változtass a szűrésen, vagy hozz létre egy új feladatot.</p>
          </div>
        )}
      </div>
    </div>
  );
}
