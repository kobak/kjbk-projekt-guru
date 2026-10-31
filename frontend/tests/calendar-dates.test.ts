import assert from "node:assert/strict";
import test from "node:test";
import { dateKey, monthDays, shiftMonth } from "../src/calendarDates.ts";

test("every month begins its grid on Monday, including Sunday-start months", () => {
  for (const year of [2024, 2026, 2027, 2100]) {
    for (let month = 0; month < 12; month++) {
      const days = monthDays(new Date(year, month, 15, 12));
      assert.equal(days.length, 42);
      assert.equal(days[0].getDay(), 1);
      assert.equal(days[6].getDay(), 0);
      assert.ok(
        days.some((day) => day.getMonth() === month && day.getDate() === 1),
      );
      for (let i = 1; i < days.length; i++) {
        const tomorrow = new Date(days[i - 1]);
        tomorrow.setDate(tomorrow.getDate() + 1);
        assert.equal(dateKey(days[i]), dateKey(tomorrow));
      }
    }
  }
  assert.equal(dateKey(monthDays(new Date(2026, 10, 1, 12))[0]), "2026-10-26");
});

test("month and year navigation clamp leap days and month ends", () => {
  assert.equal(dateKey(shiftMonth(new Date(2024, 0, 31, 12), 1)), "2024-02-29");
  assert.equal(
    dateKey(shiftMonth(new Date(2024, 1, 29, 12), 12)),
    "2025-02-28",
  );
  assert.equal(
    dateKey(shiftMonth(new Date(2026, 11, 31, 12), 1)),
    "2027-01-31",
  );
  assert.equal(
    dateKey(shiftMonth(new Date(2026, 0, 31, 12), -1)),
    "2025-12-31",
  );
});
