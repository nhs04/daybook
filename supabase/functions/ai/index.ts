// Daybook assistant: you write what you want in plain words, and it returns the actions
// that file each thing in the right place (tasks, emails, applications, chapters, courses, vision board pins).
// The page applies the actions and can undo them. Runs as a Supabase Edge Function so your
// Anthropic API key never reaches the browser.
//
// Secrets (Supabase → Edge Functions → Secrets):
//   ANTHROPIC_API_KEY  your key from console.anthropic.com (required)
//   ALLOWED_EMAIL      your email address, so only you can use the assistant (recommended)

import Anthropic from "npm:@anthropic-ai/sdk@^0.136.0";
import { createClient } from "npm:@supabase/supabase-js@2";

const RULES = `You are the assistant inside Daybook, a planner for a student's PhD thesis, PhD applications, university courses, emails to send, and a vision board.
The person writes what they want in plain words. Turn it into actions that put each thing in the right place.
Rules:
- Only do what they asked. Never invent extra items they did not mention.
- Use the ids from the snapshot ("ref") when they mean an existing university, chapter, course, task or email. Match names loosely ("harvard" is Harvard University).
- Resolve dates like "friday", "tomorrow", "next week", "dec 4" from today's date and weekday in the snapshot. Dates are YYYY-MM-DD. Leave the date null if they gave none.
- Emails they need to write: add_email with the subject in "title", the recipient in "to", and a short polite draft in "body" only if they ask for one.
- Things to do: add_task, with "place" = "apps" (university id in ref), "thesis" (chapter id in ref when it clearly fits one), "course" (course id in ref) or "none". Assignments, projects, exams, readings and meetings go in "kind" ("assignment", "project", "exam", "reading", "meeting").
- New universities: add_application. New courses: add_course. New thesis chapters: add_chapter. Thesis title, supervisor or submission deadline: update_thesis.
- Progress: "I submitted MIT" or "Harvard CV is done" is update_application (new "stage", or requirement names in "items"). "Chapter 2 is drafted" is update_chapter. "I finished X" is complete_task. "I sent the email to X" is mark_email_sent.
- Dreams, goals, quotes and words for the vision board: add_pin with "kind" goal, quote or word, the words in "text", an optional author or note in "caption", and a university id in ref when the goal is about one.
- Removing: delete_task, delete_email, delete_application, delete_chapter, delete_course or delete_pin, with the id in ref. Only remove what they clearly asked to remove; when they say "all" (for example "remove all my emails"), add one delete action per matching item.
- Changing: update_task (new "title", "date", "priority", "notes" or "kind"), update_email ("title" is the subject, "to", "date", "body"), update_application ("university", "program", "date" is the deadline, "stage", requirement names done in "items"), update_chapter ("title", "status", "date"), update_course ("title" is the name, "code", "teacher", "when"). Always put the id in ref, and leave every field you are not changing as null. Use "none" as the date to remove a date.
- "reply" is one short, warm sentence saying what you did.`;

const nullable = (schema: Record<string, unknown>) => ({ anyOf: [schema, { type: "null" }] });
const str = nullable({ type: "string" });

const ACTION = {
  type: "object",
  properties: {
    type: {
      type: "string",
      enum: [
        "add_task", "add_email", "add_application", "update_application", "add_chapter", "update_chapter",
        "add_course", "complete_task", "mark_email_sent", "add_pin", "update_thesis",
        "update_task", "update_email", "update_course",
        "delete_task", "delete_email", "delete_application", "delete_chapter", "delete_course", "delete_pin",
      ],
    },
    title: str, date: str, ref: str, to: str, body: str, notes: str, university: str, program: str,
    code: str, teacher: str, when: str, kind: str, text: str, caption: str, supervisor: str,
    place: nullable({ type: "string", enum: ["thesis", "apps", "course", "none"] }),
    stage: nullable({ type: "string", enum: ["research", "prep", "submitted", "interview", "decision"] }),
    status: nullable({ type: "string", enum: ["todo", "outline", "draft", "revise", "done"] }),
    priority: nullable({ type: "integer", enum: [1, 2, 3] }),
    items: nullable({ type: "array", items: { type: "string" } }),
  },
  required: [
    "type", "title", "date", "ref", "to", "body", "notes", "university", "program", "code", "teacher", "when",
    "kind", "text", "caption", "supervisor", "place", "stage", "status", "priority", "items",
  ],
  additionalProperties: false,
};

const SCHEMA = {
  type: "object",
  properties: { reply: { type: "string" }, actions: { type: "array", items: ACTION } },
  required: ["reply", "actions"],
  additionalProperties: false,
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const anthropic = new Anthropic(); // reads ANTHROPIC_API_KEY

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return reply({ error: "method_not_allowed" }, 405);

  // Only signed-in people (and, if set, only you) can use the assistant.
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
  });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return reply({ error: "not_signed_in" }, 401);
  const allowed = Deno.env.get("ALLOWED_EMAIL");
  if (allowed && user.email?.toLowerCase() !== allowed.toLowerCase()) return reply({ error: "not_allowed" }, 403);

  let body: { text?: unknown; context?: unknown };
  try { body = await req.json(); } catch { return reply({ error: "bad_request" }, 400); }
  const text = typeof body.text === "string" ? body.text.trim().slice(0, 4000) : "";
  const context = typeof body.context === "string" ? body.context : "";
  if (!text || !context || context.length > 80000) return reply({ error: "bad_request" }, 400);

  try {
    const response = await anthropic.beta.messages.create({
      model: "claude-opus-5-5",
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
      system: RULES,
      messages: [{ role: "user", content: `Daybook snapshot (JSON):\n${context}\n\nWhat they wrote:\n"""${text}"""` }],
    });

    if (response.stop_reason === "refusal") return reply({ reply: "I can’t help with that one.", actions: [] });
    const block = response.content.find((b) => b.type === "text");
    if (!block || block.type !== "text") return reply({ reply: "", actions: [] });
    return reply(JSON.parse(block.text));
  } catch (error) {
    if (error instanceof Anthropic.RateLimitError) return reply({ error: "rate_limited" }, 429);
    if (error instanceof Anthropic.AuthenticationError) {
      console.error("Anthropic API key is missing or wrong");
      return reply({ error: "upstream_error" }, 500);
    }
    if (error instanceof Anthropic.APIError) {
      console.error(`Anthropic API error ${error.status}: ${error.message}`);
      return reply({ error: "upstream_error" }, 502);
    }
    console.error(error);
    return reply({ error: "upstream_error" }, 500);
  }
});
