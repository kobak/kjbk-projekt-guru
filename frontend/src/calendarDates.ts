export function dateKey(date: Date): string {
  return `${String(date.getFullYear()).padStart(4, "0")}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function monthDays(month: Date): Date[] {
  const start = new Date(month);
  start.setDate(1);
  start.setHours(12, 0, 0, 0);
  start.setDate(1 - ((start.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

// Keep the day when possible, including the last day of shorter months.
export function shiftMonth(date: Date, amount: number): Date {
  const next = new Date(date);
  const day = next.getDate();
  next.setDate(1);
  next.setMonth(next.getMonth() + amount);
  const last = new Date(next);
  last.setMonth(last.getMonth() + 1, 0);
  next.setDate(Math.min(day, last.getDate()));
  return next;
}
