"""End-to-end browser tests of the conversation UI (ADR-0008, PROPOSED). Synthetic data only.

These drive the real app in Chromium against a live server on 127.0.0.1:8765 (the only origin the server's
same-origin check admits) with a mocked provider that records exactly what it receives. They need Playwright for
Python and a Chromium build (`pip install playwright` and `playwright install chromium`); without Playwright the
module is skipped, as in CI, so a CI pass is never evidence that these ran. Set SOVEREIGN_UI_SCREENSHOTS to a
directory to also save screenshots.
"""
import os
from pathlib import Path
import socket
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")
expect = sync_api.expect

from sovereign import providers   # noqa: E402
from sovereign.app import create_app   # noqa: E402

PORT = 8765
SHOTS = os.environ.get("SOVEREIGN_UI_SCREENSHOTS")
HOSTILE = "<img src=x onerror=\"document.title='pwned'\">"


def fake_generate(calls):
    def generate(provider, messages):
        calls.append({"provider": provider, "messages": messages})
        return (f"Reply {len(calls)} from {provider}.\n\n- **Lantern** keeps its readings on the device [E1]\n"
                f"- A second point\n\n{HOSTILE} and `inline code`")
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
    calls = []
    monkeypatch.setattr(providers, "available", lambda: [
        {"id": "local", "name": "Local evidence (no AI)", "cloud": False, "ready": True},
        {"id": "kimi", "name": "Kimi", "cloud": True, "ready": True},
        {"id": "openai", "name": "Openai", "cloud": True, "ready": True}])
    monkeypatch.setattr(providers, "generate", fake_generate(calls))
    app = create_app(str(tmp_path / "vault.db"))
    seeded = seed(app.state.vault)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not srv.started:
        assert time.time() < deadline, "server did not start"
        time.sleep(0.05)
    yield {"url": f"http://127.0.0.1:{PORT}", "app": app, "calls": calls, **seeded}
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


def test_forget_removes_replies_that_used_it_and_keeps_them_out_of_history(page, server):
    calls = server["calls"]
    say(page, "How does Lantern store readings?", "kimi")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 1 from kimi.")
    say(page, "Tell me about Harbor sync.")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 2 from kimi.")

    page.click("button[data-view=memory]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator(".record", has_text="Lantern stores readings in SQLite").get_by_role("button", name="Forget").click()
    expect(page.locator("#capture-status")).to_contain_text("conversations in this tab no longer show them")
    page.click("button[data-view=chat]")
    expect(page.locator(".msg.redacted")).to_have_count(1)
    expect(page.locator("#messages")).not_to_contain_text("Reply 1 from kimi.")
    expect(page.locator("#messages")).not_to_contain_text("Lantern stores readings in SQLite")
    expect(page.locator("#messages")).to_contain_text("Reply 2 from kimi.")   # it did not use the forgotten record

    say(page, "What else should I look at?")
    approve(page)
    expect(page.locator(".msg.assistant").last).to_contain_text("Reply 3 from kimi.")
    sent = str(calls[2]["messages"])
    assert "Reply 1 from kimi." not in sent and "How does Lantern store readings?" not in sent
    assert "Reply 2 from kimi." in sent


def forget(page, text):
    page.click("button[data-view=memory]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator(".record", has_text=text).get_by_role("button", name="Forget").click()
    expect(page.locator(".record", has_text=text)).to_have_count(0)
    page.click("button[data-view=chat]")


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
    forget(page, "Lantern stores readings in SQLite")       # the reply used this one, so it is removed
    expect(page.locator(".msg.redacted")).to_have_count(1)
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
