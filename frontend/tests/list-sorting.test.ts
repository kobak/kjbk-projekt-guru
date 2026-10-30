import assert from "node:assert/strict";
import test from "node:test";
import { sortListTasks } from "../src/listSorting.ts";

const tasks = [
  {
    id: "undated",
    position: 0,
    priority: "urgent" as const,
    due_date: null,
    due_time: null,
    created_at: "2026-01-05T12:00:00Z",
  },
  {
    id: "later",
    position: 1,
    priority: "low" as const,
    due_date: "2026-02-02",
    due_time: null,
    created_at: "2026-01-02T12:00:00Z",
  },
  {
    id: "morning",
    position: 2,
    priority: "normal" as const,
    due_date: "2026-02-01",
    due_time: "09:00",
    created_at: "2026-01-03T12:00:00Z",
  },
  {
    id: "afternoon",
    position: 3,
    priority: "high" as const,
    due_date: "2026-02-01",
    due_time: "14:00",
    created_at: "2026-01-01T12:00:00Z",
  },
];
const ids = (rows: typeof tasks) => rows.map((task) => task.id);
test("deadline ascending considers time and places undated tasks last", () => {
  assert.deepEqual(ids(sortListTasks(tasks, "due", [])), [
    "morning",
    "afternoon",
    "later",
    "undated",
  ]);
  assert.equal(tasks[0].id, "undated");
});
test("priority puts urgent first", () =>
  assert.deepEqual(ids(sortListTasks(tasks, "priority", [])), [
    "undated",
    "afternoon",
    "morning",
    "later",
  ]));
test("creation puts newest first", () =>
  assert.deepEqual(ids(sortListTasks(tasks, "created", [])), [
    "undated",
    "morning",
    "later",
    "afternoon",
  ]));
test("manual order is projected onto the visible subset and new tasks append", () => {
  assert.deepEqual(
    ids(sortListTasks(tasks, "manual", ["afternoon", "missing", "later"])),
    ["afternoon", "later", "undated", "morning"],
  );
  assert.deepEqual(
    ids(
      sortListTasks(
        tasks.filter((task) => task.id !== "later"),
        "manual",
        ["afternoon", "later", "morning", "undated"],
      ),
    ),
    ["afternoon", "morning", "undated"],
  );
});
test("all-day tasks come before timed deadlines on the same day", () => {
  const allDay = { ...tasks[2], id: "all-day", due_time: null };
  assert.deepEqual(ids(sortListTasks([tasks[2], allDay], "due", [])), [
    "all-day",
    "morning",
  ]);
});
