import assert from "node:assert/strict";
import test from "node:test";
import { editMentions, mentionQuery, searchable } from "../src/mentions.ts";

const mention = { user_id: 2, start: 3, end: 10 };
test("mention search uses the caret, allows full names and ignores ordinary email addresses", () => {
  assert.deepEqual(mentionQuery("Kérlek @Kiss An, később", 15, []), {
    start: 7,
    end: 15,
    search: "Kiss An",
  });
  assert.equal(mentionQuery("anna@example.com", 16, []), null);
  assert.equal(mentionQuery("👍 @Kornél ", 11, [mention]), null);
  assert.equal(searchable("Kornél ÁRVÍZTŰRŐ"), searchable("kornel arvizturo"));
});
test("inserting text before a selected mention shifts UTF-16 offsets", () => {
  assert.deepEqual(editMentions("👍 @Kornél!", "Szia 👍 @Kornél!", [mention]), [
    { ...mention, start: 8, end: 15 },
  ]);
  assert.deepEqual(
    editMentions("👍 @Kornél!", "👍 @Kornél! Rendben.", [mention]),
    [mention],
  );
});
test("changing or deleting mention text removes its notification target", () => {
  assert.deepEqual(editMentions("👍 @Kornél!", "👍 @Korné!", [mention]), []);
  assert.deepEqual(editMentions("👍 @Kornél!", "👍 !", [mention]), []);
  assert.deepEqual(editMentions("👍 @Kornél!", "@Más", [mention]), []);
});
test("edits between two mentions preserve both and shift only the latter", () => {
  const spans = [
    { user_id: 1, start: 0, end: 5 },
    { user_id: 2, start: 7, end: 12 },
  ];
  assert.deepEqual(editMentions("@Anna, @Márk", "@Anna, nézd @Márk", spans), [
    spans[0],
    { ...spans[1], start: 12, end: 17 },
  ]);
});
