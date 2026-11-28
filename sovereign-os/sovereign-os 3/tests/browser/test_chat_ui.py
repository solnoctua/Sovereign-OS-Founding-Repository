"""End-to-end browser tests of the conversation UI (ADR-0008, PROPOSED). Synthetic data only.

These drive the real app in Chromium against a live server on 127.0.0.1:8765 (the only origin the server's
same-origin check admits) with a mocked provider that records exactly what it receives. They need Playwright for
Python and a Chromium build (`pip install playwright` and `playwright install chromium`); without Playwright the
module is skipped, as in CI, so a CI pass is never evidence that these ran. Set SOVEREIGN_UI_SCREENSHOTS to a
directory to also save screenshots.
"""
import json
import os
from pathlib import Path
import re
import socket
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")
expect = sync_api.expect

from sovereign import context, providers, store   # noqa: E402
from sovereign.app import create_app   # noqa: E402

PORT = 8765
SHOTS = os.environ.get("SOVEREIGN_UI_SCREENSHOTS")
HOSTILE = "<img src=x onerror=\"document.title='pwned'\">"
STORAGE = "Lantern stores readings in SQLite on the device."
LONG = "LONG-REPLY"   # a question containing this gets a reply longer than the per-message bound, with emoji
_E1 = re.compile(r'"label": "E1",\s*"text": "([^"]*)"')


class Gate:
    """Holds the next call at one point until the test releases it (one-shot), to order asynchronous events."""
    def __init__(self):
        self._armed, self.entered, self._release = False, threading.Event(), threading.Event()

    def arm(self):
        self._armed = True
        self.entered.clear()
        self._release.clear()

    def pause(self):
        if self._armed:
            self._armed = False
            self.entered.set()
            assert self._release.wait(30), "gate never released"

    def release(self):
        self._release.set()


def fake_generate(calls, gate):
    """A recording provider whose replies carry content forward the way a real model can: it quotes the record
    labelled E1 when one is in the context, and repeats the first line of its previous reply, so a later reply can
    contain a record's text without that record being in its own context (the F-1 dependency chain)."""
    def generate(provider, messages):
        calls.append({"provider": provider, "messages": messages})
        gate.pause()
        quoted = _E1.search(messages[-1]["content"])
        earlier = [m["content"] for m in messages[1:-1] if m["role"] == "assistant"]
        line = f"Reply {len(calls)} from {provider}."
        if quoted:
            line += f" From your records: {quoted.group(1)}"
        if earlier:
            line += " As I said before: " + earlier[-1].split("\n")[0][:300]
        if LONG in messages[-1]["content"]:
            return line + "\n\n" + "Long analysis 🙂 é " * 1200 + "THE-CONCLUSION 👨‍👩‍👧"
        return line + f"\n\n- **Lantern** keeps its readings on the device [E1]\n- A second point\n\n{HOSTILE} and `inline code`"
    return generate


def seed(vault):
    storage = vault.add("Lantern stores readings in SQLite on the device.")
    battery = vault.add("Lantern battery lasts about 14 days in the field test.")
    vault.add("Harbor syncs every 5 minutes.")
    claim = vault.add_claim("Lantern battery lasts about two weeks.", [battery["id"]], "human")
    vault.transition_claim(claim["id"], "approved", None, "proposed")
    return {"storage": storage, "battery": battery, "claim": claim}


@pytest.fixture
def server(tmp_path, monkeypatch):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            pytest.fail(f"port {PORT} is in use; these tests need it (the server admits only that origin)")
    calls, provider_gate, compile_gate = [], Gate(), Gate()
    monkeypatch.setattr(providers, "available", lambda: [
        {"id": "local", "name": "Local evidence (no AI)", "cloud": False, "ready": True},
        {"id": "kimi", "name": "Kimi", "cloud": True, "ready": True},
        {"id": "openai", "name": "Openai", "cloud": True, "ready": True}])
    monkeypatch.setattr(providers, "generate", fake_generate(calls, provider_gate))
    compile_context = context.compile_context

    def gated_compile(*args, **kwargs):           # the bundle is computed now; its response is held by the gate
        bundle = compile_context(*args, **kwargs)
        compile_gate.pause()
        return bundle
    monkeypatch.setattr(context, "compile_context", gated_compile)
    app = create_app(str(tmp_path / "vault.db"))
    seeded = seed(app.state.vault)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not srv.started:
        assert time.time() < deadline, "server did not start"
        time.sleep(0.05)
    yield {"url": f"http://127.0.0.1:{PORT}", "app": app, "calls": calls, "provider_gate": provider_gate,
           "compile_gate": compile_gate, **seeded}
    provider_gate.release()
    compile_gate.release()
    srv.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


def open_page(browser, server, **context_options):
    context = browser.new_context(**{"viewport": {"width": 1280, "height": 860},
                                     "device_scale_factor": 2 if SHOTS else 1, **context_options})
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    # Script errors fail a test; Chromium's own log line for an HTTP error status (an expected 409) does not.
    page.on("console", lambda m: page.errors.append(m.text)
            if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
    page.goto(server["url"])
    expect(page.locator(".empty-state")).to_be_visible()
    return page


@pytest.fixture
def page(browser, server):
    page = open_page(browser, server)
    yield page
    errors = page.errors
    page.context.close()
    assert errors == [], errors


def shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def say(page, text, provider=None):
    if provider:
        page.select_option("#provider", provider)
    page.fill("#message", text)
    page.press("#message", "Enter")


def approve(page):
    card = page.locator(".msg.review").last
    expect(card).to_be_visible()
    card.get_by_role("button", name="Approve & send").click()


def test_local_and_cloud_turns_carry_only_approved_conversation(page, server):
    calls = server["calls"]
    expect(page.locator("#provider")).to_have_value("kimi")            # the first configured cloud model
    say(page, "Where does Lantern store readings?", "local")
    local = page.locator(".msg.local")
    expect(local).to_contain_text("no model was called")
    expect(local).to_contain_text("Lantern stores readings in SQLite on the device.")
    expect(page.locator("#chat-title")).to_have_text("Where does Lantern store readings?")
    assert calls == []

    say(page, "How does Lantern store readings?", "kimi")
    card = page.locator(".msg.review")
    expect(card).to_contain_text("Review what leaves this device → Kimi")
    expect(card.locator(".review-summary")).to_contain_text("your message and 3 items from your memory")
    expect(card.locator(".review-summary")).not_to_contain_text("earlier message")   # a local turn is never history
    expect(page.locator("#send")).to_be_disabled()                       # one pending message at a time
    card.locator("summary", has_text="Exact payload").click()
    expect(card.locator(".payload pre")).to_contain_text("MESSAGE:\nHow does Lantern store readings?")
    shot(page, "1-review-before-sending")
    assert calls == []                                                   # nothing leaves before approval
    approve(page)

    reply = page.locator(".msg.assistant:not(.local)").last
    expect(reply).to_contain_text("Reply 1 from kimi.")
    expect(reply.locator(".md li")).to_have_count(2)
    expect(reply.locator("button.cite", has_text="E1")).to_be_visible()
    expect(reply).to_contain_text(HOSTILE)                               # model output is text, never markup
    assert page.locator("#messages img").count() == 0 and page.title() == "Sovereign"
    assert [m["role"] for m in calls[0]["messages"]] == ["system", "user"]

    say(page, "And what about the battery?")
    expect(page.locator(".msg.review .review-summary")).to_contain_text("2 earlier messages of this conversation")
    approve(page)
    expect(page.locator(".msg.assistant:not(.local)").last).to_contain_text("Reply 2 from kimi.")
    sent = calls[1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "How does Lantern store readings?" and sent[2]["content"].startswith("Reply 1 from kimi.")
    assert "Where does Lantern store readings?" not in str(sent)        # the local turn stayed local
    page.locator(".msg.assistant:not(.local)").last.locator("summary", has_text="Memory used").click()
    shot(page, "2-reply-with-memory-used")

    page.locator(".msg.assistant:not(.local)").last.locator("button.cite").first.click()
    expect(page.locator("#prov-dialog")).to_be_visible()                # a citation opens its provenance
    page.click("#prov-close")


def test_carryover_is_shown_and_a_changed_vault_requires_a_new_review(page, server):
    calls = server["calls"]
    say(page, "How does Lantern store readings?", "kimi")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 1 from kimi.")

    say(page, "Summarise what we know about Lantern.", "openai")
    card = page.locator(".msg.review")
    expect(card.locator(".warn")).to_contain_text("Includes 1 earlier reply written by Kimi: approving sends it to OpenAI.")
    shot(page, "3-carryover-to-another-provider")
    # The vault changes after the preview: approval of the old plan must not send anything.
    vault = server["app"].state.vault
    vault.add("Lantern now stores readings in PostgreSQL.", supersedes_id=server["storage"]["id"])
    approve(page)
    card = page.locator(".msg.review")
    expect(card.locator(".notice")).to_contain_text("changed since the preview")
    assert len(calls) == 1                                               # the stale approval sent nothing
    expect(card.locator(".items").first).to_contain_text("PostgreSQL")   # the new context is shown for review
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 2 from openai.")
    assert calls[1]["provider"] == "openai" and calls[1]["messages"][2]["content"].startswith("Reply 1 from kimi.")


def forget(page, text):
    page.click("button[data-view=memory]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator(".record", has_text=text).get_by_role("button", name="Forget").click()
    expect(page.locator(".record", has_text=text)).to_have_count(0)
    page.click("button[data-view=chat]")


def cloud_turn(page, text, reply_number, provider=None):
    say(page, text, provider)
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text(f"Reply {reply_number} from")


def payload_text(call) -> str:
    return json.dumps(call["messages"], ensure_ascii=False)


# --- F-1: Forget clears the dependent conversation suffix (ADR-0008 §6) ---------------------------------------

def test_forget_clears_every_turn_after_the_first_that_used_it_and_keeps_earlier_ones(page, server):
    calls = server["calls"]
    cloud_turn(page, "Tell me about Harbor sync.", 1, "kimi")                 # before: unaffected, kept
    cloud_turn(page, "How does Lantern store readings?", 2)                   # uses the record; quotes it
    cloud_turn(page, "Interesting, what follows from that?", 3)               # repeats reply 2 without retrieval
    cloud_turn(page, "And then?", 4)                                          # repeats reply 3: still the record
    assert STORAGE in payload_text(calls[3])                                  # the chain really carries it
    forget(page, "Lantern stores readings in SQLite")
    messages = page.locator("#messages")
    for gone in ("Reply 3 from", "Reply 4 from", STORAGE, "How does Lantern store readings?",
                 "Interesting, what follows", "And then?", "Reply 2 from"):
        expect(messages).not_to_contain_text(gone)                            # the dependent replies too
    cleared = page.locator(".msg.cleared")
    expect(cleared).to_have_count(1)
    expect(cleared).to_contain_text("3 messages")
    expect(messages).to_contain_text("Tell me about Harbor sync.")
    expect(messages).to_contain_text("Reply 1 from kimi.")
    # The next turn, to another provider, carries only the kept exchange.
    say(page, "Summarise where we are.", "openai")
    card = page.locator(".msg.review")
    expect(card.locator(".review-summary")).to_contain_text("2 earlier messages")
    expect(card.locator(".warn").first).to_contain_text("1 earlier reply written by Kimi")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 5 from openai.")
    sent = payload_text(calls[4])
    assert STORAGE not in sent and "Reply 2 from" not in sent and "Interesting, what follows" not in sent
    assert "Reply 1 from kimi." in sent and calls[4]["provider"] == "openai"


def test_a_reply_in_flight_when_its_chain_is_forgotten_never_appears(page, server):
    calls, gate = server["calls"], server["provider_gate"]
    cloud_turn(page, "How does Lantern store readings?", 1, "kimi")
    say(page, "Interesting, what follows from that?")                       # depends on reply 1 through history
    card = page.locator(".msg.review")
    expect(card).to_be_visible()
    gate.arm()
    card.get_by_role("button", name="Approve & send").click()
    assert gate.entered.wait(10)                                              # transmitted; the reply is held
    forget(page, "Lantern stores readings in SQLite")
    with page.expect_response("**/api/ask"):
        gate.release()
    page.wait_for_timeout(300)
    expect(page.locator("#messages")).not_to_contain_text("Reply 2 from")     # the late reply stays discarded
    expect(page.locator("#messages")).not_to_contain_text(STORAGE)
    expect(page.locator(".msg.cleared")).to_contain_text("2 messages")
    cloud_turn(page, "Start again.", 3)
    assert [m["role"] for m in calls[2]["messages"]] == ["system", "user"]   # nothing cleared re-enters history


def test_a_pending_preview_in_the_chain_is_cleared_and_cannot_be_approved(page, server):
    calls = server["calls"]
    cloud_turn(page, "How does Lantern store readings?", 1, "kimi")
    say(page, "Interesting, what follows from that?")
    expect(page.locator(".msg.review")).to_be_visible()
    forget(page, "Lantern stores readings in SQLite")
    expect(page.locator(".msg.review")).to_have_count(0)
    expect(page.locator(".msg.cleared")).to_contain_text("2 messages")
    expect(page.locator("#send")).to_be_enabled()
    assert len(calls) == 1


def test_a_preview_completing_after_forget_is_discarded(page, server):
    gate = server["compile_gate"]
    cloud_turn(page, "How does Lantern store readings?", 1, "kimi")
    gate.arm()
    say(page, "Interesting, what follows from that?")
    assert gate.entered.wait(10)                                              # compiled with reply 1 as history
    forget(page, "Lantern stores readings in SQLite")
    with page.expect_response("**/api/context/compile"):
        gate.release()
    page.wait_for_timeout(300)
    expect(page.locator(".msg.review")).to_have_count(0)
    expect(page.locator("#messages")).not_to_contain_text(STORAGE)
    expect(page.locator(".msg.cleared")).to_have_count(1)


def test_only_the_newest_preparation_of_a_turn_is_kept(page, server, tmp_path):
    # The turn stays in its conversation here, so only the sequence fence can tell its two preparations apart: a
    # vault change compiles the pending review again, and the first compile, completing last, must not replace it.
    calls, gate = server["calls"], server["compile_gate"]
    gate.arm()
    say(page, "How does Lantern store readings?", "kimi")
    assert gate.entered.wait(10)                                              # the first compile is held
    other = store.Vault(str(tmp_path / "other.db"))
    other.add("Lantern stores a second copy of readings on its SD card.")
    page.click("button[data-view=memory]")
    page.set_input_files("#import-file", files=[{"name": "export.json", "mimeType": "application/json",
                                                 "buffer": json.dumps(other.export()).encode()}])
    with page.expect_response("**/api/context/compile"):                      # the second compile, not held
        page.click("#import")
    expect(page.locator("#capture-status")).to_contain_text("Imported 1 records")
    page.click("button[data-view=chat]")
    card = page.locator(".msg.review")
    expect(card.locator(".items").first).to_contain_text("SD card")
    with page.expect_response("**/api/context/compile"):                      # the first compile completes last
        gate.release()
    page.wait_for_timeout(300)
    expect(card).to_have_count(1)
    expect(card.locator(".items").first).to_contain_text("SD card")         # the newer preview is kept
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 1 from kimi.")
    assert len(calls) == 1 and "SD card" in payload_text(calls[0])           # approved and sent without a 409


def test_a_regeneration_completing_after_invalidation_does_not_reintroduce_content(page, server):
    gate = server["provider_gate"]
    cloud_turn(page, "How does Lantern store readings?", 1, "kimi")
    page.locator(".msg.assistant").last.get_by_role("button", name="Regenerate").click()
    card = page.locator(".msg.review")
    expect(card).to_be_visible()
    gate.arm()
    card.get_by_role("button", name="Approve & send").click()
    assert gate.entered.wait(10)
    forget(page, "Lantern stores readings in SQLite")
    with page.expect_response("**/api/ask"):
        gate.release()
    page.wait_for_timeout(300)
    for gone in ("Reply 1 from", "Reply 2 from", STORAGE):
        expect(page.locator("#messages")).not_to_contain_text(gone)
    expect(page.locator(".msg.cleared")).to_have_count(1)


def test_deleting_a_conversation_during_a_pending_reply_keeps_it_deleted(page, server):
    gate = server["provider_gate"]
    say(page, "How does Lantern store readings?", "kimi")
    gate.arm()
    page.locator(".msg.review").get_by_role("button", name="Approve & send").click()
    assert gate.entered.wait(10)
    page.evaluate("window.__deleted = state.chats[0]")                       # keep a handle on the deleted object
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator(".chat-item").first.locator(".chat-delete").click()
    expect(page.locator(".chat-item")).to_have_count(0)
    with page.expect_response("**/api/ask"):
        gate.release()
    page.wait_for_timeout(300)
    expect(page.locator(".chat-item")).to_have_count(0)
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from")
    assert page.evaluate("state.chats.length") == 0
    assert page.evaluate("window.__deleted.turns.every(t => !t.reply && t.status !== 'done')")   # nothing retained


def test_out_of_order_completions_land_in_their_own_conversations(page, server):
    gate = server["provider_gate"]
    say(page, "How does Lantern store readings?", "kimi")
    gate.arm()
    page.locator(".msg.review").get_by_role("button", name="Approve & send").click()
    assert gate.entered.wait(10)
    page.click("#new-chat")
    say(page, "Harbor sync interval", "local")                               # completes first
    expect(page.locator(".msg.local")).to_contain_text("Harbor syncs every 5 minutes.")
    with page.expect_response("**/api/ask"):
        gate.release()
    page.wait_for_timeout(300)
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from")    # not in the conversation on screen
    page.locator(".chat-open", has_text="How does Lantern").click()
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 1 from kimi.")


def test_deleting_a_claim_clears_the_turns_that_used_it(page, server):
    cloud_turn(page, "How long does the Lantern battery last?", 1, "kimi")   # approved claim becomes M1
    page.click("button[data-view=memory]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator(".claim", has_text="Lantern battery lasts about two weeks").get_by_role("button", name="Delete").click()
    expect(page.locator(".claim", has_text="Lantern battery lasts about two weeks")).to_have_count(0)
    page.click("button[data-view=chat]")
    expect(page.locator(".msg.cleared")).to_contain_text("a claim you have since deleted")
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from")


def test_a_trusted_restore_that_deletes_records_clears_conversations(page, server):
    cloud_turn(page, "Tell me about Harbor sync.", 1, "kimi")
    backup = server["app"].state.vault.export()
    backup["records"] = [r for r in backup["records"] if r["id"] != server["storage"]["id"]]
    backup["tombstones"] = backup.get("tombstones", []) + [{"id": server["storage"]["id"],
                                                             "deleted_at": "2026-11-28T00:00:00+00:00"}]
    page.click("button[data-view=memory]")
    page.set_input_files("#import-file", files=[{"name": "backup.json", "mimeType": "application/json",
                                                 "buffer": json.dumps(backup).encode()}])
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#restore")
    expect(page.locator("#capture-status")).to_contain_text("Restored")
    page.click("button[data-view=chat]")
    expect(page.locator(".msg.cleared")).to_contain_text("trusted restore")
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from")


# --- F-3: earlier messages left out are counted in full ---------------------------------------------------------

INJECT = """n => {
  const chat = {id: "acc-" + n, title: "Accounting " + n, turns: [], updated: Date.now()};
  for (let i = 0; i < n; i++) chat.turns.push({id: "t" + n + "-" + i, message: "Question " + i, provider: "kimi",
    pins: [], status: "done", reply: "Answer " + i, used: [], listed: [], seq: 1});
  state.chats.unshift(chat); state.activeId = chat.id; drawChatList(); drawChat();
}"""


@pytest.mark.parametrize("exchanges,sent,omitted,by_browser,by_server", [
    (40, 40, 40, 16, 24),   # the audit's case: 80 earlier messages, the browser sends 64, Sovereign keeps 40
    (41, 40, 42, 18, 24),
    (32, 40, 24, 0, 24),    # exactly the browser's limit
    (20, 40, 0, 0, 0),      # exactly the conversation budget
])
def test_omitted_earlier_messages_are_counted_across_browser_and_server(page, server, exchanges, sent, omitted,
                                                                         by_browser, by_server):
    page.evaluate(INJECT, exchanges)
    say(page, "Where are we now?", "kimi")
    card = page.locator(".msg.review")
    expect(card.locator(".review-summary")).to_contain_text(f"{sent} earlier messages of this conversation")
    if omitted:
        expect(card.locator(".omitted")).to_contain_text(
            f"{omitted} older messages of this conversation are not sent: {by_browser} left out by this browser")
        expect(card.locator(".omitted")).to_contain_text(f"{by_server} by Sovereign's conversation budget")
    else:
        expect(card.locator(".omitted")).to_have_count(0)


# --- F-2 / S3: Unicode-safe head-and-tail clipping ----------------------------------------------------------------

CLIP_CASES = """() => {
  const L = 16000, points = s => Array.from(s).length;
  const lone = s => /[\\ud800-\\udbff](?![\\udc00-\\udfff])|(?<![\\ud800-\\udbff])[\\udc00-\\udfff]/.test(s);
  const out = {};
  const emoji = "x".repeat(15919) + "😀" + "y".repeat(100);
  out.emoji = clip(emoji, L);
  out.combining = clip("e\\u0301".repeat(9000), L);
  out.family = clip("👨‍👩‍👧".repeat(4000), L);
  out.exact = clip("z".repeat(L), L) === "z".repeat(L);
  out.overBy1 = clip("z".repeat(L + 1), L);
  out.idempotent = clip(out.emoji, L) === out.emoji;
  out.loneIn = clip("a\\ud83d" + "b".repeat(20000), L);
  const report = {};
  for (const [k, v] of Object.entries(out)) report[k] = typeof v === "boolean" ? v :
    {points: points(v), lone: lone(v), head: v.slice(0, 2), tail: v.slice(-2), marker: v.includes("characters omitted by Sovereign")};
  const body = out.combining.replace(/\\n…\\[\\d+ characters omitted by Sovereign\\]…\\n/, "");
  report.combiningPairs = (body.match(/e\\u0301/g) || []).length === (body.match(/e/g) || []).length;   // no base cut from its mark
  report.familyIntact = !/\\u200d(?![\\ud83d])/.test(out.family) && out.family.replace(/\\n…\\[\\d+ characters omitted by Sovereign\\]…\\n/, "").split("👨‍👩‍👧").join("") === "";
  return report;
}"""


def test_clipping_is_unicode_safe_bounded_head_and_tail_and_idempotent(page, server):
    r = page.evaluate(CLIP_CASES)
    for key in ("emoji", "combining", "family", "overBy1", "loneIn"):
        assert r[key]["points"] <= 16000 and not r[key]["lone"] and r[key]["marker"], (key, r[key])
    assert r["emoji"]["head"] == "xx" and r["emoji"]["tail"] == "yy"             # head and tail both kept
    assert r["exact"] and r["idempotent"] and r["combiningPairs"] and r["familyIntact"]


def test_a_long_emoji_reply_becomes_valid_clipped_history_sent_exactly_as_previewed(page, server):
    calls = server["calls"]
    cloud_turn(page, f"Give me the {LONG} version please.", 1, "kimi")
    say(page, "Now summarise it.")
    card = page.locator(".msg.review")
    expect(card.locator(".review-summary")).to_contain_text("2 earlier messages")
    expect(card.locator(".omitted")).to_contain_text("1 earlier message was shortened")
    card.locator("summary", has_text="Exact payload").click()
    expect(card.locator(".payload pre")).to_contain_text("characters omitted by Sovereign")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 2 from kimi.")
    reply = calls[1]["messages"][2]["content"]
    assert len(reply) <= 16000 and "THE-CONCLUSION" in reply and reply.startswith("Reply 1 from kimi.")


# --- S1: a missed search is not evidence of absence -------------------------------------------------------------

def test_a_local_search_with_no_match_does_not_claim_absence(page, server):
    say(page, "What did I decide about the sailing boat?", "local")
    expect(page.locator(".msg.local")).to_contain_text("No eligible record matched this message's words")
    expect(page.locator(".msg.local")).to_contain_text("can still exist")


def test_a_reply_stays_traceable_after_an_earlier_forget_dropped_its_details(page, server):
    server["app"].state.vault.add("Lantern sensitive prototype note.", "sensitive")
    say(page, "How does Lantern store readings?", "kimi")
    expect(page.locator(".msg.review")).to_contain_text("Considered but not used")   # the sensitive note stays here
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 1 from kimi.")
    forget(page, "Lantern sensitive prototype note.")       # the reply only listed it: its details go, the reply stays
    expect(page.locator("#messages")).to_contain_text("Reply 1 from kimi.")
    expect(page.locator("#messages")).to_contain_text("Memory details for this reply were removed")
    expect(page.locator("#messages")).not_to_contain_text("Lantern sensitive prototype note.")
    forget(page, "Lantern stores readings in SQLite")       # the reply used this one, so it is cleared
    expect(page.locator(".msg.cleared")).to_have_count(1)
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from kimi.")


def test_conversations_list_search_and_nothing_in_browser_storage(page, server):
    say(page, "Where does Lantern store readings?", "local")
    expect(page.locator(".msg.local")).to_be_visible()
    page.click("#new-chat")
    expect(page.locator(".empty-state")).to_be_visible()
    say(page, "Harbor sync interval", "local")
    expect(page.locator(".msg.local")).to_contain_text("Harbor syncs every 5 minutes.")
    expect(page.locator(".chat-item")).to_have_count(2)
    page.fill("#chat-search", "harbor")
    expect(page.locator(".chat-item")).to_have_count(1)
    page.fill("#chat-search", "")
    page.locator(".chat-open", has_text="Where does Lantern").click()
    expect(page.locator("#chat-title")).to_have_text("Where does Lantern store readings?")
    shot(page, "4-conversations")
    stored = page.evaluate("async () => [localStorage.length, sessionStorage.length,"
                           " (await indexedDB.databases()).length, document.cookie]")
    assert stored == [0, 0, 0, ""]
    page.reload()
    expect(page.locator(".empty-state")).to_be_visible()                 # conversations lived only in the tab
    expect(page.locator(".chat-list")).to_contain_text("No conversations yet.")


def test_phone_width_has_a_drawer_and_no_horizontal_scroll(browser, server):
    page = open_page(browser, server, viewport={"width": 390, "height": 844})
    try:
        assert page.locator("#sidebar").bounding_box()["x"] < 0
        page.click("#toggle-sidebar")
        expect(page.locator("#new-chat")).to_be_in_viewport()
        page.mouse.click(370, 420)                                       # tapping outside the drawer closes it
        expect(page.locator("#new-chat")).not_to_be_in_viewport()
        page.click("#toggle-sidebar")
        expect(page.locator("#new-chat")).to_be_in_viewport()
        page.click("#new-chat")
        say(page, "Where does Lantern store readings?", "local")
        expect(page.locator(".msg.local")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.click("#toggle-sidebar")
        page.click("button[data-view=memory]")
        expect(page.locator("#memory-view")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.errors == []
    finally:
        page.context.close()
