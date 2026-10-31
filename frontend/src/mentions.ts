export type Mention = { user_id: number; start: number; end: number };
export const mentionName = (name: string) => name.trim().replace(/\s+/g, " ");
export const searchable = (text: string) =>
  text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("hu-HU");

export function mentionQuery(body: string, caret: number, mentions: Mention[]) {
  const match = /(^|[\s(])@([^@\n]{0,100})$/.exec(body.slice(0, caret));
  if (!match) return null;
  const start = caret - match[2].length - 1;
  if (mentions.some((mention) => mention.start <= start && mention.end > start))
    return null;
  return { start, end: caret, search: match[2] };
}

// Offsets use UTF-16, just like textarea selectionStart and String.slice.
// Edits through a mention turn it back into ordinary text.
export function editMentions(
  before: string,
  after: string,
  mentions: Mention[],
): Mention[] {
  let start = 0;
  while (
    start < before.length &&
    start < after.length &&
    before[start] === after[start]
  )
    start++;
  let oldEnd = before.length,
    newEnd = after.length;
  while (
    oldEnd > start &&
    newEnd > start &&
    before[oldEnd - 1] === after[newEnd - 1]
  ) {
    oldEnd--;
    newEnd--;
  }
  return mentions.flatMap((mention) => {
    if (mention.end <= start) return [mention];
    if (mention.start >= oldEnd)
      return [
        {
          ...mention,
          start: mention.start + newEnd - oldEnd,
          end: mention.end + newEnd - oldEnd,
        },
      ];
    return [];
  });
}
