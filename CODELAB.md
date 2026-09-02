author: Annie Wang (cuppibla)
summary: One creator, one channel, three videos. Open a studio, publish with one press, then teach the channel to make the next video better — long-running waits that survive dead processes, a graph you grow out of one prompt, and state layers ending in BigQuery and Memory Bank.
id: vibestudio
categories: adk,agents,bigquery,memory-bank,gemini
environments: Web
status: Draft
feedback link: https://github.com/cuppibla/vibe-studio-lab/issues

# Long-Running Workflows & Durable State with ADK

## Introduction
Duration: 0:03:00

![The studio, breathing — one lamp waiting, the state safely in jars](codelab-img/hero.gif)

**You open a studio, make one video, press one button — and then teach the
channel to make the next one better than you would have.**

Making a video is a long-running business. Every station of it waits on
something the agent doesn't control: the avatar render waits on an image
model, the creative form waits on YOU, the shots wait on a farm, and the
audience answers tomorrow. So the agent's real job is **waiting well** —
pause without keeping a process alive, ask you things mid-flight, and
remember what matters when it comes back.

Here is the graph you will grow, run, and publish through — every box is
real code you will read:

![The workflow](codelab-img/d1-workflow.png)

The lab is **three acts**, and every chapter belongs to exactly one:

| act | chapters | what you do | what it teaches |
|---|---|---|---|
| **I · Your studio** | ⏳ 🪞 | make your channel's face; change it without re-describing it | long running is human-in-the-loop · multi-turn is stable because of agent state |
| **II · Your first video** | 🔀 🗺️ 🏁 | run the channel as ONE prompt, grow the real graph out of it, publish with one press | why a workflow, felt before told · the same hinge under every pause |
| **III · The channel improves** | 💾 🌍 🧠 | turn on the feeds: your prefs, the audience graph, the channel's lessons | each lap's video is visibly better — and no process stayed alive between laps |

Five things thread every chapter, and the codelab points at each one as it
passes: one **hinge** (every pause resolves as a `function_response` with
the same call id), one set of **nodes** (the small apps and the final lap
run the same imported functions), one **topic** (you type it once, it
becomes your published video), one **face** (your avatar travels to the
room), and one **policy word** (you add it early; it guards your real
publish).

One law carries the whole lab: **a long-running agent is defined by where its
state lives, because its process is allowed to die.**

## 🧰 Setup
Duration: 0:09:00

This is the whole app's architecture — look at it before touching anything:

![Vibe Studio architecture — frontend, backend, inspector, cloud](codelab-img/d5-architecture.png)

👀 What the picture shows: **Vibe Studio** (left) is the frontend — every
button on it just runs one of your backend commands. **Your backend** is the
middle box: two agents (the workflow and the render desk), the plain-python
drivers, and the `runs/` files where every wait and key lives on disk.
**adk web** (bottom) writes nothing — it reads the same `sessions.db` and
shows you raw events. And the **cloud** column is where durable state ends
up: the agent cites BigQuery and recalls Memory Bank. You will boot each
piece right before its first use.

- **What** — clone, install, and prove the toolchain is green. Nothing gets booted here.
- **Why** — every server in this lab starts right before the first step that needs it, so when a surface opens you know exactly which command owns it.
- **How** — one command block → read the map.

### Who is who

You are building the **backend** of a creator studio. `agent/` is that
backend. **Vibe Studio** (port 4600) is the frontend someone already built
for it — every button just runs one of your backend commands, and the grey
caption under each button names which one. **adk web** (port 8000) is the
inspector: it shows the raw events your backend writes, nothing more.

### Install

👉💻 In the Cloud Shell terminal (call it **tab 1** — every 👉💻 in this lab
means tab 1 unless it says otherwise). One block, and the last line proves
everything works:

```console
git clone https://github.com/cuppibla/vibe-studio-lab
cd vibe-studio-lab
uv sync
source .venv/bin/activate
cp .env.example .env
python scripts/preflight.py
```

*You should see* every line tick (Vibe Studio reports `not running yet` —
correct: the app chapter 🗺️ boots it), ending in `PREFLIGHT GREEN`.

### Join the room (optional — live workshops)

If an instructor announced platform values, put them in `.env` now — this
is the ONLY setup the shared platform ever needs. From the publish chapter
on, every video you finish also premieres to the room's VibeTube,
silently, and your published card carries the watch link.

👉💻 In **tab 1**, open `.env` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/.env
```

👉✏️ Fill the platform block (the third line is how the room credits you):

```
VIBETUBE_URL=https://<the-platform-url-your-instructor-gives>
VIBETUBE_EVENT=sandbox
VIBETUBE_NAME=Your Name
```

Self-paced, no instructor? **Skip this** — leave the block commented out.
Everything in the lab works local-only, and preflight prints
`room: not configured (local only — publishing still works)`, which is
green. (Re-run `python scripts/preflight.py` after filling it and you get
`✓ room: connected` instead.)

### Read more (optional)

<aside class="positive">
<b>The repo, one breath.</b> <code>agent/</code> is the backend you'll read
and lightly edit · <code>vibestudio/</code> is an 8-line adk web entry ·
<code>stage0_prompt/ … stage4_gates/</code> are the five apps the workflow
act grows through (chapters 🔀 🗺️) · <code>app/</code> is Vibe Studio
(given) · <code>world/</code> is the render farm + platform (given) ·
<code>bqgraph/</code> is the graph chapter 🌍 · <code>checks/</code> holds
the verification gates.
</aside>

<aside class="positive">
<b>Gates: how you verify a chapter.</b> <code>python -m checks.check
&lt;name&gt;</code> runs ~10 labeled assertions against the REAL artifacts
(sessions, state, the wall, BigQuery, the bank) — never a source grep. Green
means the chapter's idea physically happened. Each chapter's Read more names
its gate, they are all optional, and <code>cloudshell edit
~/vibe-studio-lab/checks/check.py</code> lets you read any of them — reviewing the gate you
just passed is a fine way to review the chapter.
</aside>

## ⏳ Your avatar — the agent waits, you answer
Duration: 0:07:00
![LongRunningFunctionTool — the job goes out, the receipt comes back](codelab-img/d6-lrft.png)

👀 What the picture shows: your text reaches the desk, the desk calls its
ONE tool — and the wrapper does two things in the same instant: the job
leaves for the studio (green), and a receipt comes straight back (orange).
The agent says WAITING and the turn is OVER. No blocking, no thread — the
only trace is a row in `sessions.db`. You are about to live this exact
picture, and the job leaving is a real image model drawing your face.


- **What** — ask a raw agent for YOUR creator avatar, watch it stop without finishing while a real image model works elsewhere, kill the server to prove the wait survived — then end the wait yourself, by hand.
- **Why** — the lab's load-bearing idea in one chapter: *pending is a value in the session log, not a thread in memory* — and every wait ends the same way: someone answers by id. Today that someone is you. That is all "human in the loop" is.
- **How** — read the agent → boot adk web → describe your avatar → watch WAITING → kill and restart → answer the pending call.

### Who you are about to talk to

👉💻 In **tab 1**, open `agent.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/vibestudio/agent.py
```

👉📖 In `vibestudio/agent.py` — read only, nothing to change — the whole
file is two meaningful lines:

```python
from agent.desk import render_desk

root_agent = render_desk
```

- `root_agent = render_desk` — adk web looks for a folder with an
  `agent.py` exporting `root_agent`; that is the entire discovery
  convention, and the folder name (`vibestudio`) becomes the app name.
- `render_desk` itself lives in `agent/desk.py` — open that one too.

👉💻 In **tab 1**, open `desk.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/agent/desk.py
```

👉📖 In `desk.py` — read only, nothing to change — look at the tool list.
This line is the chapter's vocabulary word:

```python
    tools=[LongRunningFunctionTool(render_submit)],
```

**`LongRunningFunctionTool`** is the vocabulary word of this chapter: it
wraps a plain function and tells ADK "this tool returns a RECEIPT
immediately; the real result comes later." The desk wraps two of them —
`avatar_submit` (the portrait studio, which you are about to use) and
`render_submit` (the shot farm, which the workflow uses later). That one
wrapper is what makes the wait you are about to see possible. This desk is not a practice dummy: **in the publish chapter (🏁)
it is the exact agent that renders your video's three shots.** Here you meet it alone, to
see one wait clearly.

### What you are about to do, in order

1. read the 8-line agent you are about to talk to (editor, **tab 1**)
2. start `adk web` in a **second** terminal tab — and leave that tab alone
3. open it in the browser and type one line: `Make my avatar: a cute cat`
4. watch it stop at **WAITING** — and read why
5. kill the dev UI and start it again — the wait is still there
6. type `{"status": "done"}` into the response box under the pending call
7. watch the desk wake up and say **AVATAR READY** — you were the human in the loop

Everything you need is spelled out below; the explanations come after each
action, not before.

### Start adk web (the dev UI)

👉💻 Open a **second terminal tab (tab 2)** and start ADK's dev UI:

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
adk web . --port 8000 --allow_origins "*" --reload_agents --session_service_uri "sqlite+aiosqlite:///$PWD/runs/sessions.db"
```

👉🔬 Click **Web Preview → Change port → 8000**, then click **Select an
app** at the top left and pick **`vibestudio`**:

![adk web, fresh — pick vibestudio from the app list](codelab-img/s1-devui-landing.png)

👀 Every folder holding an `agent.py` that exports `root_agent` shows up in
that list — that is the whole discovery convention. `vibestudio` is this
studio's desk; the five `stage*` apps are the pieces of the channel's
graph you will grow through in chapters 🔀 and 🗺️.

### Type the slow request

👉🔬 In the chat box, ask for **your own avatar** — the face your channel
will wear for the rest of this lab. **Two or three words are enough**: name
a creature, not a style.

Copy any one of these, or write your own after the colon:

```
Make my avatar: a cute cat
```

```
Make my avatar: a red panda
```

```
Make my avatar: a grumpy owl
```

```
Make my avatar: a small red robot in a hoodie
```

The part after `Make my avatar:` is **yours** — that is the only text the
studio takes from you.

👀 Why so short? Because the studio owns the look, not you. The tool builds
the real prompt in three layers, and only the first one contains your
words:

| layer | who writes it | what it does |
|---|---|---|
| **ANCHOR** | you | *"The character is: a cute cat"* |
| **STYLE-LOCK** | the studio | low-poly facets · the cream/terracotta/sage palette · soft studio light |
| **CONSTRAINTS** | the studio | head-and-shoulders, centered, square, plain cream background, no text |

Everyone in the room types something different and everyone gets the same
house style — that is what a style-lock is for. (You will read the code in
the next chapter.)

*You should see* one tool call, the word **WAITING** — and then nothing. No
spinner, no progress bar. The turn is over:

![The wait, as data — the call, the pending receipt, WAITING](codelab-img/s1-avatar-waiting.png)

👀 Click the `avatar_submit` call: its response is literally
`{"status": "pending", "job_id": "por_…", …}`. `pending` is not an error and
not a promise object — it is a **value inside a normal response**, sitting
in the session log.

And this is the part worth pausing on: **a real job is running right now, in
a process the agent does not own.** `avatar_submit` started a detached
worker that is calling an image model — 20 to 30 seconds of genuine work —
and then returned instantly. The agent has nothing left to do; the
invocation ended honestly; your portrait is being drawn anyway.

👀 One more thing to notice for later: under that call sits a small box,
**"Enter your response…"**. Leave it alone for now — the next chapter is
you typing into it.

👉🔬 Ask the obvious thing — type exactly this:

```
is it done yet?
```

*You should see* **WAITING** again. Talking to the agent does not finish the
render — text never resumes a wait.

### Kill it

👉💻 In **tab 2** (the terminal running adk web), press **Ctrl+C** — the
entire dev UI dies. Now start it again — same block as before (pressing ↑
then Enter retypes the last line for you):

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
adk web . --port 8000 --allow_origins "*" --reload_agents --session_service_uri "sqlite+aiosqlite:///$PWD/runs/sessions.db"
```

👉🔬 Reload the Preview, pick **`vibestudio`** again, then reopen your
session from the **NEW SESSION ▾** picker. Everything is still there: the call, the pending receipt, your
unanswered question. **The wait is a row in `runs/sessions.db`. It does not
need any process to exist.**

### You be the human in the loop

👀 The studio finished your portrait long ago — but nothing tells the
agent. ADK never polls the studio; no callback is registered anywhere.
Someone must **deliver the result back into the session**, addressed by
that call's id. Right now, that someone is you — by hand, in the dev UI.

👉🔬 Under the pending `avatar_submit` call sits a small input,
**"Enter your response…"** — ADK's built-in way to answer a long-running
call. Type exactly this and press the send arrow:

```
{"status": "done"}
```

That is the entire message. You are not carrying the picture — the studio
already wrote it to disk and recorded it. All the session needs is *"that
call is finished"*, addressed to the right id.

*You should see* the desk wake up and reply **AVATAR READY**:

![You delivered it by hand — your response, then the desk continuing](codelab-img/s2-avatar-delivered.png)

👀 Read the two new rows. The first is a *user* turn that contains no text
at all — only a `function_response` carrying the SAME call id. The second
is the desk, awake again, answering with the finished map. Nothing
restarted; nothing was waiting in memory. You typed a value into a row,
and a conversation that ended minutes ago picked up mid-sentence.

**This is the chapter's headline: every long-running wait ends the same
way — someone answers by id. Today that someone was you, and that is all
"human in the loop" is.** Later a form and a button send this exact
message for you — same hinge, nicer clothes.

*What you learned:* pending is a value in the session log, not a thread in
memory — the process may die, the wait survives; and resume = one
`function_response` with the same call id, no matter who sends it.

### Read more (optional)

![What long-running actually means — five moments, one surviving row](codelab-img/d3-longrunning.png)

👀 The whole chapter as one picture: ① you ask · ② the pending receipt
lands in `sessions.db` (the shelf) · ③ the turn ends with nothing running ·
④ you kill the server — the row does not care · ⑤ any process delivers the
result with the SAME call id, and the conversation continues.

<aside class="positive">
<b>How anything finds an open wait.</b> The event that carries a
long-running call also carries <code>long_running_tool_ids</code>. Scan a
session's events, collect those ids, keep the LATEST response per id — the
ones still saying <code>pending</code> are the open waits. That scan is
~15 lines in <code>agent/drive.py pending()</code>, and it is how the
delivery helper, the publish chapter's worker, and the Studio UI all
find work to do.
</aside>

<aside class="negative">
<b>Why "is it done yet?" changes nothing.</b> Your text arrives as a NEW
user turn — the model can chat back, but the pending <code>function_call</code>
is a separate open item that only a <code>function_response</code> with its
id can close. Prose and results ride different rails.
</aside>

<aside class="positive">
<b>The same delivery, as a script.</b> You typed the result; a real system
polls for it. <code>agent/deliver.py</code> is that script in 40 lines:
FIND the newest session holding a pending call → WAIT until the studio (or
the farm) says done → SEND via <code>drive.answer(...)</code>. Try it on a
second avatar: type another <code>Make my avatar: …</code> in adk web, leave
the response box alone, then in <b>tab 1</b> run:

<pre><code>cd ~/vibe-studio-lab
source .venv/bin/activate
python -m agent.deliver</code></pre>

Our real run printed
<code>── result delivered (same id) → the run continued ──</code> and the
session moved on by itself. Read it with
<code>cloudshell edit ~/vibe-studio-lab/agent/deliver.py</code> — the only
ADK in the whole file is the three lines the next chapter's Read more shows.
</aside>

<aside class="positive">
<b>Is a delivery script normal? Yes — it always exists.</b> Every
long-running system has this process under some name: the queue
<b>worker</b>, the <b>webhook handler</b>, the nightly <b>reconciler</b>.
ADK deliberately ships only the primitives — pending calls in a session,
<code>function_response</code> to resume — because the process that connects
them to YOUR world (your farm, your review queue, your clock) is always
application code. In production, this file is a Cloud Run job or a webhook
target.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check one</code>. It asserts that your typed session really carries a long-running call AND that it was answered by id — the whole chapter, physically proven in sessions.db. Nothing later depends on running this.
</aside>

## 🪞 Change it without re-describing — agent state
Duration: 0:05:00

- **What** — ask for ONE change to your avatar, get the same character back — then read why: the state that carried it, in the order that matters.
- **Why** — multi-turn conversations are fragile, because the process that answered turn 1 is allowed to be GONE by turn 2. **Agent state is what makes multi-turn stable**: the continuity lives at an address outside the process.
- **How** — one more request → deliver it → ask "why is it still the same cat?" → read the state callback → see it in the State tab → read the world's own ledger → compare the two portraits.

### Turn 2 — change it without describing it again

👉🔬 In the chat box, ask for one change. Again: short. `Give my avatar
a tiny party hat` · `add round glasses` · `put it in a circular frame`:

```
Give my avatar a tiny party hat
```

*You should see* the same shape as before — a call, a pending receipt,
WAITING. Deliver it the same way when the studio is done (`{"status":
"done"}` in the response box), and the desk says **AVATAR READY** again.

### Why is it still the same cat?

👀 Sit with the question, because it is the chapter. The obvious way to
keep a character consistent is a chat session that remembers — but the
worker that drew turn 1 *exited minutes ago*, and its memory went with it
(it is as dead as the server you killed last chapter). Nothing that
"remembered" your cat was running when turn 2 started. So the continuity
came from somewhere else — from **state with an address outside the
process**, and it has two layers. Read them in order of authority.

### Layer 1 · the agent's own state — a callback

👀 ADK gives the agent a specific place to write what it wants to keep: a
**callback**. `agent/desk.py` ends with this, and it runs after every turn
the desk takes:

```python
def remember_avatar(callback_context) -> None:
    from world import portrait
    latest = portrait.latest()
    if not latest:
        return
    state, url, who = callback_context.state, latest["url"], portrait.anchor(latest)
    if state.get("user:avatar") != url or state.get("user:avatar_anchor") != who:
        state["user:avatar"] = url          # user: = this user, every session
        state["user:avatar_anchor"] = who   # the words that started it, from the ledger
```

Three things to take from it:

- **`callback_context.state` is writable.** Assign to it and ADK turns the
  change into a *state delta* on the event log — no save call, no database
  code. (This desk uses `after_agent_callback`; there are
  before/after hooks for the agent, the model and every tool.)
- **The `user:` prefix picks the lifetime.** These keys belong to the user,
  not to this conversation — that one word is doing quiet work here, and a
  whole chapter (💾) later hangs on it.
- **It is idempotent.** It compares before writing, so a hundred turns
  produce one delta.

👉🔬 See it: click the **State** tab on the left of the dev UI (browse only,
nothing to type):

![The callback's work — user:avatar written beside the two-turn story](codelab-img/s2-avatar-state.png)

### Layer 2 · the world's own ledger — a file

👀 The agent's state says *which* portrait is yours. The pixels themselves,
and the parent-child link between turn 1 and turn 2, live in the WORLD's
own records: a PNG on disk and a row in `runs/portraits.json` saying which
job it came from. Here is the code that uses them — `world/portrait.py`,
inside `_generate()`:

```python
    parent = _load()["jobs"].get(job.get("parent") or "", {})
    parent_png = (config.ROOT / "app" / parent.get("url", "").lstrip("/")
                  if parent.get("url", "").startswith(WEB) else None)
    if parent_png and parent_png.exists():
        # TURN 2 - the previous image IS the context; no re-describing the character
        contents = [gt.Part.from_bytes(data=parent_png.read_bytes(),
                                       mime_type="image/png"),
                    change_prompt(job["description"])]
    else:
        contents = portrait_prompt(job["description"])
```

Read the branch: no parent → build the layered prompt from scratch. Has a
parent → **load that file from disk** and send the bytes back to the model
with the change. The ledger row is the only thing that knows they are
related.

### Look at what you waited for

Both portraits are on disk now. One trip to the editor and you can see them.

<aside class="negative">
<b>Use tab 1 — not the tab running adk web.</b> Tab 2 is busy with the dev
UI; pressing Ctrl+C there would close the session you have been typing into.
Open a terminal that is idle (tab 1, the one you installed in) for the
command below.
</aside>

👉💻 In **tab 1**, open the folder the studio writes into — the Cloud Shell
Editor previews images, so click the two newest PNGs:

```console
cloudshell edit ~/vibe-studio-lab/app/static/avatars
```

*Our run typed "a cute cat", then asked for a hat:*

![Turn 1 and turn 2 — the character survived, because a file did](codelab-img/s2-avatar-multiturn.png)

<aside class="positive">
<b>What about the video shots later?</b> Chapter 🏁 renders three shots
through the same mechanism, but that farm is <b>prebaked</b>
(<code>world/broker.py</code> answers on a fixed clock) — three real renders
would cost you half an hour. Your avatar is the real thing in this lab: a
genuine model call, genuinely slow, genuinely yours.
</aside>

One last thing to notice before you move on: **you will never type that
JSON again.** From here the app's buttons, the repair agent and the deadline
all send the same message for you — same shape, same call id, a human in
the loop only where a human belongs.

*What you learned:* multi-turn becomes stable when the state that carries
it has an address outside the process — the agent's own state (a callback
writing `user:` keys) plus the world's ledger (a file). In-process memory
is neither. You will see that face wearing the app in two chapters, and on
the room's platform when you publish.

### Read more (optional)

**The three lines behind the send button.** Everything above resumed through
one function — `answer()` in `agent/drive.py`
(`cloudshell edit ~/vibe-studio-lab/agent/drive.py`):

<!-- code: RESUME -->
```python
    part = gtypes.Part(function_response=gtypes.FunctionResponse(
        id=call_id, name=name, response=response))
    return await _drive(node, session_id, [part], user_id)
```

A `Part` carrying a **`FunctionResponse`** with the **same `id`**, driven
into the session as a new message. That is the whole delivery path: the dev
UI does it when you press send, and every driver in this lab calls this
function. Ten lines above it live two names worth keeping —
`Runner(app_name=…, session_service=svc(), auto_create_session=True)` (the
Runner drives) and `svc() = DatabaseSessionService(db_url=…)` (the
SessionService remembers).

<aside class="negative">
<b>Why the workflow never holds machine waits.</b> A resumed graph
<b>re-runs its nodes</b> — an external submit inside a node would submit
(and pay) twice. That's why machines wait in a plain session (the desk) and
graphs pause only for people: re-asking a person is safe; re-charging a
render is not. The publish chapter 🏁 shows the two working together.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check one</code>. It asserts the wait existed AND every call was answered by id — both avatar turns, physically proven in sessions.db. Nothing later depends on running this.
</aside>

## 🔀 From one prompt to a pipeline
Duration: 0:11:00

- **What** — run the WHOLE channel as one prompt and feel exactly where it hurts; then grow the channel's real graph out of it, stage by stage, in the dev UI you already have open.
- **Why** — "why a workflow" should be felt before it is told. And there is only ONE workflow in this lab — the channel's: every stage below is that graph, met in pieces. The small apps import the same node functions the finished channel runs.
- **How** — same adk web tab, walk the app dropdown: `stage0_prompt` → `stage1_fanout` → `stage2_pause`. Pick tonight's topic before you start — the thing you would actually film. It rides through every stage and becomes your published video.

### The production line you are about to grow

![The production line — a graph for research, the world for renders, a second graph for shipping](codelab-img/d10-productionline.png)

👀 Study the three bands for ten seconds, no more. **Top band** — the lap
graph: research fans out → one join → a topic desk → *a pause that waits
for you* → a script. That band is what the stages below grow, and its edge
list is the one you will write at the EDGES hole. **Middle band** —
deliberately NOT a graph: the renders wait with the desk from ⏳ in a
plain session, and you approve the thumbnail there, because a resumed
graph re-runs its nodes and a render must not submit twice. **Bottom
band** — a second, smaller workflow: the publish gates. You will put its
decision core on a test bench in the next chapter, and watch it guard
your real publish after that.

### The whole channel as one prompt

👉🌐 Go back to the **browser tab with adk web** — port 8000, still running
in **tab 2** since chapter ⏳, so there is nothing to restart. If you closed
that terminal tab, start it again:

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
adk web . --port 8000 --allow_origins "*" --reload_agents --session_service_uri "sqlite+aiosqlite:///$PWD/runs/sessions.db"
```

👉🌐 (If you had to restart: **Web Preview → Change port → 8000**.) At the
**top left** is the app dropdown that says `vibestudio`. Switch it to
**`stage0_prompt`**.

👉💻 In **tab 1**, open the file — read the instruction before you run it:

```console
cloudshell edit ~/vibe-studio-lab/stage0_prompt/agent.py
```

👉📖 In `stage0_prompt/agent.py` — read only, nothing to change — the
instruction is the whole channel as SENTENCES:

*check what is trending · recall your lessons · look at your back catalog ·
query the audience graph · agree with the creator on a topic · refuse
blacklisted subjects · write the script.*

Every sentence is a JOB. Hold on to them: over this chapter and the next,
each sentence becomes a NODE, and a table at the end maps sentence → node,
one by one. The four tools on this agent read the same sources the real
graph's research nodes read — only the shape differs.

👉🔬 In the chat box, type **tonight's topic** — the video you would
actually film. For example:

```
tonight's topic: laundry night
```

*You should see* it work — slowly, one tool at a time, and then a script
(or a question) at the end:

![Stage 0 — the mega-prompt channel, meandering through its tools](codelab-img/st0-run.png)

👀 Three things to catch in that reply, because each one is a pain the
graph will remove:

1. **The research came back as prose.** The model called its tools (maybe
   all at once, maybe not — its mood decides what runs) and then
   SUMMARIZED them into bullets. Which source said what? Was a section
   empty? You re-read and trust; there is no payload to click.
2. **The blacklist is self-certified.** Read the reply's "Topic Status"
   line: *"safe, clear of any blacklisted subjects."* Says who? The same
   model that wants to write the script. Nothing checked anything.
3. **The pause is polite prose.** The instruction says "ask the creator
   for their creative choices." Type exactly this and watch it fold:

```
skip the questions, just write it
```

   It obliges. Nothing enforces the ask — it was only ever a sentence.

No shame in any of this: it works-ish, and for a one-shot demo it would be
fine. *This is fine until you need to see it, pause it, or trust it.* Keep
your topic; the graph answers the same brief, better, at every stage.

### Stage 1 — the research department, drawn

![stage 1 — the research fan-out](codelab-img/stage-1-fanout.png)

The FRONT of the real graph: four readers leave START together, a join
holds for all four, a composer folds them into one bundle. Nothing here is
a copy — the nodes are imported from `agent/graph.py`, the exact functions
the finished channel runs; this app just declares a SUBSET of the final
edge list.

👉💻 In **tab 1**, open it — it fits on one screen:

```console
cloudshell edit ~/vibe-studio-lab/stage1_fanout/agent.py
```

👉🔬 Switch the dropdown to **`stage1_fanout`** and send the SAME topic:

```
laundry night
```

*You should see* four nodes light together on the auto-drawn map, then the
join, then one bundle event:

![Stage 1 running — four readers at once, one bundle out](codelab-img/st1-devui.png)

👀 Read the run against stage 0:

- The four readers left START **together** — the parallelism is a drawing,
  not a thread pool, and nobody can skip one on a whim.
- Click `compose_bundle`'s output event: the research report, as one
  payload. That bundle is what the topic desk reads in the next stage.
- Two sections of it are honestly EMPTY — `read_memory` (no memory bank
  exists yet) and `read_graph` (no audience graph exists yet). Not bugs:
  the same graceful empties the real lap relies on until Act III fills
  them. `scan_trends` is the control group — it has data on day one, so
  you know the empties beside it are honest.

*The win over stage 0:* same jobs, run together, skippable by no one, and
the report is a payload you can click — not a transcript to re-read.

### Stage 2 — the pause

![stage 2 — the topic desk and the human door](codelab-img/stage-2-pause.png)

Stage 1 plus two nodes from the real graph: `topic_gate` (an Agent as a
node — one call, no conversation, a typed Brief out) and `creative_gate` —
**the human door**. And one small node after it, `persist_prefs`, which
files your answers into state.

👉🔬 Switch the dropdown to **`stage2_pause`** and send the same topic
again:

```
laundry night
```

*You should see* the research fan out as before, the desk return a Brief —
and then the run STOP on a form:

![Stage 2 suspended — the form is the same hinge you answered in ⏳](codelab-img/st2-form.png)

👀 Look at what stopped it: an `adk_request_input` event, rendered by the
dev UI as a real form (subject · character · style). This is the response
box from ⏳ **wearing clothes** — same hinge, a schema riding it. What the
solo prompt could be talked out of, the graph physically cannot skip: no
`function_response`, no script.

**Do not answer it yet.** The wait has a property worth proving first.

👉💻 In **tab 2** (the terminal running adk web), press **Ctrl+C** — the
whole dev UI dies mid-pause. Now start it again — the same block as
always, typed fresh:

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
adk web . --port 8000 --allow_origins "*" --reload_agents --session_service_uri "sqlite+aiosqlite:///$PWD/runs/sessions.db"
```

👉🔬 Reload the Preview, pick **`stage2_pause`**, reopen your session from
the **NEW SESSION ▾** picker — and there is the form, still standing:

![Killed and restarted — the suspended run is still waiting at the form](codelab-img/st2-survive.png)

👀 A suspended graph is not a paused program — it is a ROW. The form
survived a dead server exactly the way your avatar's wait did, because it
is the same mechanism.

👉🔬 Now fill it — subject, character, style, your taste — and press
**Submit**. The run continues: your answers land in state and the run ends
at `persist_prefs`. (On resume the research nodes re-ran — they only read,
so re-running is safe. That is precisely why people-pauses are legal
inside a graph and machine waits are not.)

*What you learned:* the graph's own long-running moment is a pause that
survives death; a form is a schema riding the ⏳ hinge; and an
un-skippable ask is a NODE, not a sentence.

### Read more (optional)

<aside class="positive">
<b>Why the topic desk never chatted with you.</b> An <code>LlmAgent</code>
has a <code>mode</code>, and there are three:
<code>chat</code> (a normal conversational agent),
<code>single_turn</code> (one call, no conversation) and
<code>task</code> (it converses until it calls its built-in
<code>finish_task</code>). The default flips with context: a plain agent is
<code>chat</code>; <b>an agent used as a workflow node is
<code>single_turn</code></b> — which is why <code>topic_gate</code> decided
in one call. Set <code>mode="task"</code> on that node and it would pitch,
listen and revise before releasing a typed Brief.
</aside>

<aside class="positive">
<b>Where a node's arguments come from.</b> A function node binds its
parameters from the run's state by default — that is
<code>parameter_binding='state'</code>. The parameter named
<code>node_input</code> is the exception: it always holds what the
previous node returned. That is how the readers' outputs reached the join
and how the Brief reached the door.
</aside>

<aside class="positive">
<b>The stage apps are yours to break.</b> They are ordinary folders,
nothing else imports them, and no gate checks them. Add a node, change an
edge, re-run — <code>--reload_agents</code> picks it up. The stage
pictures above are generated from the same objects by
<code>scripts/shape_maps.py</code>; change the graph and the picture
changes.
</aside>

## 🗺️ Finish the graph, run the lap
Duration: 0:12:00

- **What** — grow the last two pieces (the script tail, then the publish gates on a test bench), read the replacement table, write the real edge list yourself, boot Vibe Studio and run the whole graph as a lap.
- **Why** — this is where "the small workflows" and "the real workflow" turn out to be the same thing: stage 3 IS the lap graph, the EDGES hole is a recital of it, and the app is just the graph with buttons.
- **How** — stage 3 → stage 4 (+ your policy word) → the replacement table → the EDGES hole → boot the app → start a lap → answer the form on the live map.

### Stage 3 — the script, and the graph is complete

![stage 3 — the complete lap graph](codelab-img/stage-3-script.png)

Stage 2 plus `scripter` (a second Agent-as-node) and `store_script` — and
that is the COMPLETE lap graph, edge for edge.

👉💻 In **tab 1**:

```console
cloudshell edit ~/vibe-studio-lab/stage3_script/agent.py
```

👉📖 Read the edge list at the bottom — six lines. Remember the shape; you
will write exactly this into the real file in a few minutes.

👉🔬 Switch the dropdown to **`stage3_script`**, send the same topic, fill
the form when it pauses (same three fields), press **Submit** — and this
time the run continues past your answers into a script:

![Stage 3 — past the pause and into a real script](codelab-img/st3-script.png)

👀 "Why a script" answers itself here, at the END of the growth — not at
the start. The script is what everything upstream was FOR: real readings →
the desk's typed Brief → your creative choices → the channel's constraints,
landing in one deliverable the render farm needs next. `store_script`
files it in the ledger with its **evidence citations** — the lineage the
publish gates are about to read.

### Stage 4 — the gates, on a test bench

![stage 4 — the publish decision core](codelab-img/stage-4-gates.png)

The channel has exactly TWO routers, and both are in this app, imported
from `agent/post.py` — the workflow that will ship your video: 
`policy_check` (**OK / BLOCK**) and `eval_gate` (**PASS / FAIL**). The lap
graph you just completed has ZERO routers — it ships nothing, so it needs
no gate. Both gates stand in front of the ONE side effect.

Two pieces of test equipment frame them, and neither is a fake:
`try_title` turns the line you type into the script-under-test (gates are
tested with crafted inputs before they guard real traffic), and
`hold_for_publish` stands in `publisher`'s seat — it CANNOT run here,
because no renders exist yet. That is the lesson, said out loud: the
decision core is pure and testable without the world; the side-effect
nodes (`editor`, `publisher`) wait for the publish chapter.

👉🔬 Switch the dropdown to **`stage4_gates`** and send a clean title:

```
Robot does the dishes
```

*You should see* `route: OK`, then `route: PASS`, then
`cleared_for_publish: true` — the happy path, with the route on every
edge chip.

**Now make the policy yours.** The blacklist is not code — it is a data
file the gate reads at DECISION time.

👉💻 In **tab 1**, open it:

```console
cloudshell edit ~/vibe-studio-lab/agent/policy_words.txt
```

👉✏️ Add ONE line at the bottom with a word you choose — our run added
`cliffhanger`. Save with Ctrl+S. No restart, nothing to reload: the very
next run reads the new list.

👉🔬 Back in adk web, send a title that contains your word:

```
Robot ends on a cliffhanger
```

![Stage 4 — route: BLOCK, on the word you added](codelab-img/st4-block.png)

👀 `route: BLOCK` → `quarantine` → `published: false` — and `eval_gate`
never ran, because the BLOCK edge does not pass through it. **That is what
a router is:** whether something ships is an *edge you can read*, not a
sentence in a prompt asking a model to be careful. This is not a sandbox
rule, either — in the publish chapter, this same file guards your real
video, and `lineage.gates` will show your word in the list that judged it.

### The replacement table

Every sentence of stage 0's prompt is now accounted for. This table is the
chapter — read it slowly once:

| the prompt sentence (stage 0) | replaced by | what you gained |
|---|---|---|
| "check trends · recall lessons · back catalog · audience graph" | 4 reader nodes + `join_research` | they run TOGETHER, and none can be skipped |
| "agree with the creator on a topic" | `topic_gate` → `creative_gate` (`RequestInput`) | a pause nothing can talk its way past — and it survives a dead server |
| "refuse blacklisted subjects" | `policy_check` + a labeled edge + `policy_words.txt` | a refusal you can read in lineage, not hope for |
| "write the script" | `scripter` (an Agent, as a node) | the model still writes — inside a shape you can debug |
| the prompt's silent glue ("then… then…") | the edge list | the order is a drawing, not a mood |

### The EDGES hole — write the graph you grew

The real file's nodes all exist. Its **edge list does not** — and after
three stages of running it in pieces, writing it is a recital, not a leap.

👉💻 In **tab 1**, open `graph.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/agent/graph.py
```

👉✏️ In `graph.py`, find the line marked `TODO: EDGES`, **delete** it and
**uncomment** the six lines below it (select them, Ctrl+/). The edge list
becomes:

<!-- code: EDGES -->
```python
        (START, scan_trends, join_research),
        (START, read_memory, join_research),
        (START, read_backcatalog, join_research),
        (START, read_graph, join_research),
        (join_research, compose_bundle, topic_gate, creative_gate,
         persist_prefs, scripter, store_script),
```

That is stage 3's list, in your own hand, in the real file. Why it
matters: **the Studio app's driver imports `wf` from this file** — until
you write its edges, the product has no graph to run. The stage apps
declared their own edge lists, which is why they ran while this one was
still empty.

👉 In `creative_gate`, the following code suspends the graph for a
person — you have now answered it three times, in two costumes:

<!-- code: CREATIVE_GATE -->
```python
    yield RequestInput(
        message="Creative brief - pick the subject, character, and style.",
        response_schema=CREATIVE_SCHEMA,
        payload={"topic": node_input.topic, "angle": node_input.angle,
                 "defaults": prefs})
```

A node that yields **`RequestInput`** suspends the graph — and the
**`response_schema`** is exactly what a frontend renders as a form. Forms
are not UI magic; they are schemas riding an interrupt.

### Boot the frontend

The stages ran in the inspector: no product, no buttons. The lap runs in
**Vibe Studio** — the same graph, wearing an app. **Nothing gets
stopped:** adk web stays up on port 8000; Vibe Studio is a *different*
server on 4600.

👉💻 Open a **third terminal tab (tab 3)** — leave tabs 1 and 2 alone — and
start the ONE app server. This is the boot command behind every 👉🌐 step
from here on:

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
uvicorn app.main:app --port 4600
```

| tab | what runs there | what it is |
|---|---|---|
| **tab 1** | nothing, on purpose | your work terminal — every 👉💻 command and `cloudshell edit` |
| **tab 2** | `adk web` :8000 | the inspector — raw events, the State tab, the stage apps |
| **tab 3** | `uvicorn` :4600 | Vibe Studio — the product: buttons, the form, the live map |

👉🌐 Click **Web Preview → Change port → 4600**. Nothing to type yet — but
look at the **top-right corner** before you look at anything else:

![The studio, wearing your face](codelab-img/s2-avatar-payoff.png)

👀 That is the portrait you waited for in Act I, and no code copied it
there: the app simply reads the studio's ledger
(`app/main.py` → `my_avatar()` → `world/portrait.latest()`). One long-running
job, delivered by call id, and your channel has an identity that outlives
every process in this lab.

Now the app itself, still asleep:

![Vibe Studio asleep — the idle card](codelab-img/s2-idle.png)

### Start a lap

👉🌐 On the Now card, type **the same topic you have used all chapter** as
your hint, then press **Start a lap ▸**. **Watch the map that appears
above the card** — that is the graph you just wrote, live, with your
avatar standing on whichever node the run is at:

```
laundry night
```

*You should see* the four research nodes light up together, then
`join_research` and `compose_bundle`, and — within ~20 seconds — your face
parked on `creative_gate` with a form underneath it:

![The live map — research done, and your avatar waiting at creative_gate](codelab-img/s2-flow-form.png)

👀 Two things about that map, because both are the point of this chapter:

- **It is not a drawing.** The nodes and edges are dumped from the live
  `Workflow` object — `wf.graph.edges`, where every edge carries
  `from_node.name` and `to_node.name`. The layout table only says *where* to
  put a node; if the graph ever gains a node the layout forgot, it still
  renders, listed underneath. The map can be ugly; it cannot lie.
  (`cloudshell edit ~/vibe-studio-lab/app/flowmap.py`)
- **It is not a progress bar.** A node turns solid when the node that owns
  it actually wrote its part of the run — the app reads `runs/state.json`,
  nothing is on a timer. Two nodes can turn **amber with a YOU badge**:
  those are the ones that stop and wait for a human.

👉🌐 Fill the form — it is stage 2's form in the product's clothes; the
footer even names what the click really is: one `function_response`, the
same hinge as your avatar. Press **Resume ▸**. The graph picks up where it
suspended and ends on the **Script ready** card.

### Before and after

One table closes the act — stage 0 on the left, the lap you just ran on
the right:

| the prompt (stage 0) did | the graph just did |
|---|---|
| research folded into prose you re-read | 4 nodes, one clickable payload each, a join that counts |
| asked for your taste — or didn't | suspended on a schema; you HAD to answer |
| a blacklist it hopefully remembered | a labeled edge reading a policy file |
| a transcript to re-read | a live map with your face on the current node |

*What you learned:* the stages were never warm-ups — they were the real
graph, met in pieces; the EDGES hole was a recital; and the product is the
same graph with buttons.

### Read more (optional)

<aside class="positive">
<b>⚠️ NO DEFAULT on the diamond.</b> adk web flags a router that has no
fallback edge (you can see the tag on both diamonds in the stage-4 map):
if <code>policy_check</code> ever returned a word that is neither
<code>OK</code> nor <code>BLOCK</code>, the run would have nowhere to go.
One more dict entry fixes it —
<code>{"OK": eval_gate, "BLOCK": quarantine, DEFAULT_ROUTE: quarantine}</code>
(import <code>DEFAULT_ROUTE</code> from <code>google.adk.workflow</code>).
</aside>

<aside class="positive">
<b>JoinNode.</b> The four research branches converge on a
<code>JoinNode</code> — the graph holds until all four have reported, then
<code>compose_bundle</code> runs once with everything. That join is
built-in and structural; the join you'll <i>own</i> (business "all done")
comes in the publish chapter 🏁.
</aside>

<aside class="positive">
<b>The form is really a schema.</b> <code>CREATIVE_SCHEMA</code> lists three
fields; Studio renders them as inputs and a dropdown, and adk web rendered
the SAME schema as the plainer form you used in the stages. Change the
schema and both forms change — there is no form code in either frontend.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check workflow</code>. It asserts the graph ran with real evidence and the human pause was answered by id. Nothing later depends on running this.
</aside>

## 🏁 Publish — one press
Duration: 0:07:00

- **What** — collect everything this lap is still waiting on — three machine renders and one answer from you — then publish through the gates you bench-tested in 🗺️. One press puts the video on your channel (and, if Setup joined a room, on the room's VibeTube — silently).
- **Why** — this is where the lab's threads meet. ⏳ taught you that a wait is a *value*, delivered by id. 🔀 🗺️ taught you that a run is a *shape*. Neither of them knows when a lap is **finished** — that part is yours, and it is two lines.
- **How** — read the join → Render → Approve → press Finish → watch it publish → read the gates that allowed it.

👀 Where you are: the graph stopped at the form and handed you a script.
Since then the **desk** has been holding three machine waits (the ⏳
mechanism, three at once) and the app has been holding one question for
**you**. ADK will deliver all four answers by id. It will never tell you
they add up to "done".

### The join (read, don't write)

👉💻 In **tab 1**, open `joinlogic.py` in the Cloud Shell Editor by
running:

```console
cloudshell edit ~/vibe-studio-lab/agent/joinlogic.py
```

👉📖 In `joinlogic.py` — read only, nothing to change — find
`try_finish()`. These two lines define "all done":

<!-- code: JOIN_CONDITION -->
```python
    still = drive.run(drive.pending(desk_sid(st)))
    human_ok = any(a["kind"] == "thumb" for a in st["lineage"]["approvals"])
```

*No render still pending* AND *the human approved the thumbnail*. Three
machine results and one human answer land in any order; ADK only delivers
them by id — **counting is yours**, and this is all counting takes.

### Render, approve, finish

👉🌐 You are on the **Script ready** card (yours will show your own title):

![The Script ready card — press Render when you are ready](codelab-img/s2c-script-ready.png)

Press **Render ▸**. Three renders submit in one turn, and a real thumbnail
is generated from your form choices (~20 seconds).

👉🌐 The card flips to **Ship this thumbnail?** — that picture came from your
subject + character + style. Press **Approve**:

![The human approval — a thumbnail generated from your choices, one click](codelab-img/s2-thumb-approve.png)

👉🌐 The card now shows **Rendering 0/3** with a **Finish ▸** button — the
grey caption under it says exactly what the button runs:

![Rendering 0/3 — nothing moves until a result is delivered; the Finish button is the worker](codelab-img/s2c-finish-card.png)

👀 Before pressing it, see what that button actually executes — the core
loop of `agent/finish.py`, the file the caption names:

```python
    while time.time() - t0 < config.DEADLINE_S + 25:
        jobs = {j["id"]: j for j in broker.poll()}
        for cid, name, resp in drive.run(drive.pending(sid)):
            ...
            if job["status"] == "done":
                joinlogic.handle_done(cid, name, resp, job)
            elif job["status"] == "failed":
                joinlogic.handle_failed(cid, name, resp, job)
        ...
        if joinlogic.try_finish() is not None:
            break
```

Poll the farm → deliver each finished result by call id (`handle_done` runs
the same three-line delivery ⏳ taught) → send failures to the repair agent →
and after every round, ask `try_finish()` — the two lines you just read —
whether the run is complete. In production this loop is a queue worker, a
webhook handler, a nightly reconciler.

👉🌐 Press **Finish ▸**. When the card flips to **On the wall.**, the lap is
published:

![Published — the panel is watching, and the room can see you](codelab-img/s2c-published-v2.png)

👀 If Setup joined a room, the card carries one extra line: **"and the
room can see you"** with a watch link. Nothing asked you, and no step was
skipped — the same press that put the video on your wall also premiered it
to the room's VibeTube, wearing your avatar, because publishing to the
room is part of what Finish means once `.env` points at one. Click the
link (just browse) and your card sits in the grid next to everyone else's.
(Self-paced, no room: the line simply is not there.)

👉🌐 Open the **Channel** tab and press **play** on your newest card:

![Your video on the wall — a real mp4, playable](codelab-img/s2c-channel-play.png)

👀 That is a genuine file: 1280×720 H.264, six seconds, written to
`app/static/renders/final_<run>.mp4` by post-production and served by this
same app. It was cut from the thumbnail your brief generated — the render
farm's own clips stay prebaked (see the 🪞 chapter's note), so this is the
one artifact in the lab that is really encoded, and it is the one your
audience "watches".

### The gates from the test bench, firing for real

👀 Everything after the join ran through the workflow whose decision core
you bench-tested in stage 4 — `agent/post.py`, this time at full size and
on real traffic:

![The gates deciding whether your video ships](codelab-img/shape-4-post.png)

`editor` cut the shots together, `policy_check` read `policy_words.txt` —
**the list with YOUR word in it** — and returned a route (**OK**, so
`eval_gate` ran; **BLOCK** would have sent it to `quarantine` instead), and
`eval_gate` returned **PASS**, which is the only edge that reaches
`publisher`. Two of those four branches never ship anything — and that is
the point of a deterministic router: *the decision to cause a side effect is
an edge you can read, not a sentence you hope the model meant.*

👉🔬 Want the receipts? The routes it took are recorded in the run's
lineage — `runs/state.json` → `lineage.gates` holds the policy result and
the eval checks it passed, which is exactly what the gate below asserts.
The rule you wrote on the test bench just judged your real publish.

*What you learned:* the two kinds of wait met here — three machine results
delivered by id, one human answer through the same hinge — and **"all done"
was two lines you could read**, because ADK counts nothing for you. Then the
**gates** decided this particular video was allowed to ship, and one press
published it everywhere it belongs. Act II whole: *a long-running agent is
a shape that pauses, plus the small amount of your own code that says when
the pausing is over.*

### Read more (optional)

<aside class="positive">
<b>Why <code>post</code> is a second workflow and not a node inside the
first.</b> In shape ③ you nested one workflow inside another, which is the
right move when the inner shape is pure compute. This one is not: a resumed
graph <b>re-runs its nodes</b>, and <code>publisher</code> causes a side
effect. So the lap's graph ends at the script, the world (renders, your
approval) happens outside it, and <code>wf_post</code> runs once, after —
its own <code>Runner</code>, its own session id
(<code>&lt;run_id&gt;_post</code>). Nest for shape; separate for side
effects.
</aside>

<aside class="positive">
<b>The medic and the deadline, explained.</b> One render fails QC — the
worker hands the failed prompt to a one-shot repair agent
(<code>prompt_medic</code>), which rewrites it; the retake is submitted
<i>inside the wait</i>, no restart. One render never finishes — at
<code>STUDIO_DEADLINE_S</code> the worker stops waiting and delivers a
prebaked stand-in instead. Failures repaired mid-wait, stragglers bounded by
a clock: that is what "waiting well" means in production.
</aside>

<aside class="positive">
<b>Publish is idempotent, and the gate proves it by doing it.</b> The
publish POST carries an <code>Idempotency-Key</code>; replaying the same
request returns the ORIGINAL video id instead of creating a duplicate. The
<code>lap</code> gate literally re-sends the POST and asserts the same id
comes back.
</aside>

<aside class="positive">
<b>How the silent room premiere works.</b> After the wall publish succeeds,
<code>joinlogic.try_finish</code> calls
<code>premiere.publish_to_room()</code>: ffmpeg packages your generated
thumbnail into a real 6-second H.264 poster video (~5s), then ONE multipart
POST — title, description, your display name, the video, the thumbnail,
and your avatar — to
<code>POST /api/events/&lt;room&gt;/videos</code>. No SDK, no session: a
platform is a contract. Re-running the same lap REPLACES your entry (same
<code>projectId</code>), so retries are safe. Read it with
<code>cloudshell edit ~/vibe-studio-lab/agent/premiere.py</code>.
</aside>

<aside class="negative">
<b>If the room says no, the lap does not care.</b> A room failure can never
fail your publish — the card just shows <code>room: skipped (…)</code>
with the platform's reason. <code>403</code> = the room's upload window is
closed (the instructor owns those times) · <code>413</code> = over the
limits (50 MB video, 5 MB images) · <code>404</code> = wrong room code.
Fix <code>.env</code> or wait for the window, then re-post by hand:
<code>python -m agent.premiere</code> (tab 1) — the loud back-door that
does exactly what Finish did silently.
</aside>

Want to watch the full story as text instead of pressing the button? On
any LATER lap (🌍 or 🧠): after pressing **Render ▸** and **Approve**,
do NOT press **Finish ▸**. Go to **tab 1** (your work terminal) and type:

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
python -m agent.finish
```

Exactly what the button runs — but in the terminal it narrates every
delivery as it happens:

```
── result delivered: job_0 ──
── qc FAIL: job_1 (overexposed frames in the opening seconds) -> prompt_medic ──
  medic: Specified soft, evenly balanced diffused lighting …
── deadline: job_2 replaced by prebaked stand-in ──
── result delivered: job_3 ──
── join complete (renders N/N + human) -> post-production ──
PUBLISHED: {'published': True, 'video_id': 'v_…', 'url': '/watch/v_…'}
```

Dev-UI deep dive — the whole lap as raw events (browse only, nothing to
type): port 8000 Preview → add `&userId=creator` to the URL and reload (adk
web files YOUR chats under user `user`; the lap's sessions belong to
`creator`) → **NEW SESSION ▾** → newest `run_…_wf` session. Top to bottom:
the typed Brief the topic node returned in one call, the
`adk_request_input` carrying your form's schema, your answers coming back as
a `function_response`, `user:prefs` and `choices` landing in state, and the
script.

![One lap in raw events — the Brief, the pause, your answer, the script](codelab-img/s2-adkweb-wf.png)

Then the newest `run_…_desk` session: three `render_submit` calls in one
turn, results delivered out of order, the medic's retake, the final map.

![The desk — results out of order, the medic's retake, the final map](codelab-img/s2-adkweb-desk.png)

<aside class="negative">
<b>Two gotchas, both deliberate.</b> ① adk web files NEW chats under user
<code>user</code>, while the lap's sessions live under <code>creator</code>
— that's why browsing them needs <code>&userId=creator</code> in the URL.
② The renders you just watched never lived in the graph: a resumed graph
re-runs its nodes, and an external submit inside a node would submit twice.
People-pauses are safe to re-ask; world side effects are not.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check lap</code>. It asserts four things at once: the graph ran with real evidence · both human pauses were answered by id · every render result was delivered · publish passed gates and is idempotent (it re-sends the POST and expects the SAME video back). Nothing later depends on running this.
</aside>

## 💾 The channel remembers you — session state and the user: prefix
Duration: 0:07:00

![Where state lives while the agent waits — every write and read of one lap](codelab-img/d4-state.png)

👀 What the picture shows: the left column is ONE lap, top to bottom; the
right column is the five storage layers. Solid arrows are writes — events
and your prefs into `sessions.db`, the ledger into `state.json`, rows into
BigQuery, notes into Memory Bank. Dashed arrows are reads, and they all
feed the NEXT lap: the prefilled form, the graph readings, the recalled
notes. And during the wait itself? Nothing runs — and nothing is lost.

**Act III begins: the channel improves.** Your first video is published;
the graph never changes again. What changes, one chapter at a time, is
what the graph KNOWS when it wakes up — and the first improvement is the
simplest: the channel stops re-asking you the same three questions.
This lap is your channel's **second video**.

This chapter's single lesson, up front: **ADK session state
persists in the SessionService** — here that is `DatabaseSessionService`,
i.e. the file `runs/sessions.db` — **and one key prefix (`user:`) widens a
value's lifetime from one session to all of a user's sessions.** (You have
already seen the prefix working: `user:avatar`, written by the callback in
🪞.) Everything below just makes you SEE that. Same three questions as
every layer:

- **The layer** — session files: `runs/sessions.db` and `runs/state.json`, the two files on disk that hold every wait, every event, every key.
- **Why this layer** — the process is allowed to die; whatever must outlive it needs an address outside the process.
- **How it connects** — nothing to connect: ADK's SessionService writes here automatically (you passed its sqlite URI to adk web in the first chapter ⏳).
- **How the agent uses it** — every resume reads it; and after your one-prefix edit, the next lap's form arrives pre-filled from `user:prefs`.

### The ladder

👀 Top to bottom — shorter lives above, longer below. Read the third
column twice: durable state is not an abstraction, it is a THING with an
address —

| lives for | who writes it | where it physically is |
|---|---|---|
| one turn | the model | nowhere — RAM of one call, gone at turn end |
| one process + | ADK, automatically | **one sqlite file**: `runs/sessions.db` — events, `session.state`, `user:` keys, every pending call |
| one run | your driver | **one JSON file**: `runs/state.json` — open it with any editor |
| the world | the platform | **a BigQuery dataset** (`vibestudio`) in YOUR cloud project |
| the channel | `learn`, distilled | **a managed resource**: `projects/…/reasoningEngines/<id>` (Memory Bank) |

👉🌐 Studio's **State** tab is this table, live (just browse):

![The ladder, live — five lifetimes, and what each is holding right now](codelab-img/s3-state.png)

### The kill test

👀 One law, one keystroke: the process may die; the state does not. Reading
that ten times is worth less than killing something once.

👉💻 Go to **tab 3** — the terminal running Vibe Studio — and press
**Ctrl+C**. The server is gone; the browser tab goes blank on its next
refresh.

👉💻 That terminal is free now, so use it to look at what outlived the
server. This folder **is** your durable state:

```console
ls runs
```

*Our real run:*

```
broker.json        graph_run.log     portraits.json   sessions.db
delivered.json     memorybank.json   radar.json       state.json
graph_report.json  premiere_….mp4    ui_busy.json     wall.db
```

👉💻 Start the app again, same tab, same venv (press ↑ twice, or retype):

```console
uvicorn app.main:app --port 4600
```

👉🌐 Reload the browser and open the **State** tab: every row is exactly as
you left it — the open call, your prefs, the wall. Nothing was written "on
the way out", because nothing was ever only in memory.

👀 That's it. Your avatar is in there too — `runs/portraits.json` is the
ledger that let turn 2 find turn 1's picture after its process had died.
The wait from the ⏳ chapter is a row inside `sessions.db`. The
lap's brief and script are keys inside `state.json`. The wall's watch rows
are in `wall.db`. `memorybank.json` holds one line — the ADDRESS of the
cloud resource where notes live. Kill any process you like; these files
don't care. The only two rungs NOT in this folder are the cloud ones:
the BigQuery dataset (🌍) and the Memory Bank resource itself
(🧠) — they survive even `rm -rf` of this whole VM.

### Where ADK state actually lives (read, don't write)

👀 Three sentences, and you already met every piece: a node **writes** by
yielding `Event(state={…})` — the delta rides the event log, which is why it
replays and survives. Anything in the session **reads** `session.state` —
both State tabs are just reading it. And the **SessionService stores** it —
the `DatabaseSessionService` from 🪞's Read more, the same sqlite URI you
passed to adk web. The production swap is one line: `VertexAiSessionService`, and the same
events, waits, and state live in managed Agent Engine sessions — your agent
code does not change.

### One prefix up (your second edit)

👉💻 In **tab 1**, open `graph.py` in the Cloud Shell Editor by
running:

```console
cloudshell edit ~/vibe-studio-lab/agent/graph.py
```

👉✏️ In `graph.py`, locate `persist_prefs`, **delete** the line marked
`TODO: PREFS` and **uncomment** the line below it, so the write becomes:

```
    yield Event(state={"user:prefs": node_input, "choices": node_input})
```

The only change that matters is the prefix **`user:`** — keys wearing it are
scoped to the user across ALL sessions. Same database, one word, one
lifetime longer. (`temp:` goes the other way: never persisted.)

### Watch it come back

👉🌐 All buttons this time, no terminal, nothing to type. On the **Now**
tab: press **Start next lap ▸**, wait ~20 s while the research fans out —
and the creative form arrives **pre-filled with last lap's choices**:

![A new lap, a new topic — and the form already knows your answers](codelab-img/s3-prefilled-form.png)

👉🌐 Finish the lap: press **Resume ▸** (keep or edit the pre-filled
answers), then **Render ▸**, then **Approve**, then **Finish ▸**.

👉🔬 See the same thing in the raw store — browse only, no commands, no
typing, five clicks:

1. **Web Preview → Change port → 8000** (adk web is still running in
   tab 2 — if you closed the preview tab, this reopens it).
2. Click the browser's address bar, go to the very END of the URL, add
   `&userId=creator`, press Enter. (Your own chats live under user `user`;
   the app's laps live under user `creator` — this switches the view.)
3. Click the **NEW SESSION ▾** picker at the top.
4. The session list opens — these are the app's laps. Click the newest
   `run_…_wf` session (largest number):

![Step 4 — the picker lists the app's sessions once userId=creator is in the URL](codelab-img/s3-devui-picker.png)

5. Click the **State** tab on the left panel — `user:prefs` sits right next
   to the plain keys:

![One store, two lifetimes — user:prefs beside the run's plain keys](codelab-img/s3-adkweb-state.png)

*What you learned:* ADK session state persists in the SessionService (the
file `runs/sessions.db` — that is what `DatabaseSessionService` means), and
the `user:` prefix widened your choices' lifetime from one session to every
session this user owns.

<aside class="positive">
<b>What the next video does differently:</b> the form arrives already
filled with your taste — the channel remembers YOU.
</aside>

<aside class="positive">
<b>So where IS durable state? Five answers, memorize them.</b> ① The turn:
nowhere — it dies with the model call. ② Sessions, state, waits: the file
<code>runs/sessions.db</code>. ③ The run's ledger: the file
<code>runs/state.json</code>. ④ The world's rows: the
<code>vibestudio</code> dataset in your BigQuery project. ⑤ The channel's
lessons: the Memory Bank resource
<code>projects/…/reasoningEngines/&lt;id&gt;</code>. Two files, two cloud
residents, one nothing — that is the entire answer.
</aside>

### Read more (optional)

<aside class="positive">
<b>How a write actually travels.</b> A node yields
<code>Event(state={"user:prefs": …})</code> → the delta is committed to the
event log in <code>sessions.db</code> → the SessionService folds it into
<code>session.state</code> → any later session for the same user sees the
<code>user:</code> keys. Nothing writes "directly" to state; everything
rides an event, which is why it replays and survives.
</aside>

<aside class="positive">
<b>The production swap, spelled out.</b> <code>svc()</code> is one line:
<code>DatabaseSessionService(db_url=…)</code>. Replace it with ADK's
<code>VertexAiSessionService</code> (and point adk web's
<code>--session_service_uri</code> at your Agent Engine) and the SAME
events, deltas, and pending calls live in managed cloud sessions — the
rungs are pluggable stores, not different programs. Your agent code does
not change by one character.
</aside>

<aside class="negative">
<b>The other two prefixes.</b> <code>temp:</code> keys are never persisted
at all — scratch space that dies with the invocation. <code>app:</code>
keys are shared across ALL users of the app. Wrong prefix = wrong lifetime;
the gate below catches the classic mistake (a <code>temp:</code> key that
leaked into the store).
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check state</code>. It asserts that `user:prefs` is readable from a brand-new session, matches what you typed, and no `temp:` key ever leaked into the store. Nothing later depends on running this.
</aside>

## 🌍 The channel reads its audience — the world graph (BigQuery)
Duration: 0:06:00

![BigQuery graph context — four node tables, three edges](codelab-img/d8-graph.png)

👀 What the picture shows: the four cards are plain BigQuery tables that
already exist; the three arrows are the edges the DDL declares over them —
creators publish videos, videos are about topics, viewers watch videos.
The orange `watched` edge is the one that matters: the retention numbers
(`watched_ms`, `drop_ms`) live ON the edge itself. And the channel's
questions are paths across this picture — one hop for "where do I lose
people", three hops for "what else do my finishers finish".

**Improvement #2 — the channel's third feed comes online.** `read_graph`
has been in your graph since stage 1, honestly returning empty on every
lap. This chapter builds what it reads — and this lap, your channel's
next video, is the first whose brief carries **evidence with names**.

- **The layer** — the world's rows: a BigQuery dataset (`vibestudio`) in YOUR cloud project.
- **Why this layer** — the audience's watch data is bigger than any process and shared with every tool; it outlives even this VM.
- **How it connects** — one button in the app's **World** tab (it runs `scripts/graph.sh`): create the dataset, load the vendor pack, declare the graph, push YOUR rows in.
- **How the agent uses it** — the `read_graph` research node queries it every lap; at the end of this chapter you watch the app cite it.

### Why BigQuery, and do you even need a graph

👀 **Why BigQuery for world state?** The audience's watch rows are the
platform's data, not your agent's: bigger than any process, shared with
every other tool, alive after `state.json` is deleted. That is
warehouse-shaped data — the wall's sqlite is this lab's stand-in for it.

👀 **Do you need a graph database?** No — and notice that you are not
getting one. `taste_graph` is a *declaration over tables you already have*:
nothing is copied, nothing new is deployed. Two questions decide whether
declaring it earns its keep:

| ask this | in this lab |
|---|---|
| **How many hops is the question?** | "where do I lose people" is one hop, so it stays plain SQL — the report literally tags it `engine: sql`. "what else do my finishers finish" is three hops (me → video ← viewer → video → topic): that is where one `MATCH` beats a pyramid of joins. |
| **Does the relationship itself carry data?** | `watched_ms` and `drop_ms` belong to neither the viewer nor the video — they belong to the *watch*. Retention lives on the edge. |

Many-to-many on its own does **not** justify a graph; a join table handles
that fine. Multi-hop questions over many-to-many edges do.

### The edge that carries the data (read, don't write)

👉💻 In **tab 1**, open `load.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/bqgraph/load.py
```

👉📖 In `load.py` — read only, nothing to change — find `GRAPH_DDL`. The
four tables are declared as nodes; then comes the edge that carries the
watch data, and it is three clauses long:

<!-- code: EDGE_TABLE -->
```sql
    `{d}.watched` AS watched
      KEY (viewer_id, video_id)
      SOURCE KEY (viewer_id) REFERENCES viewers (id)
      DESTINATION KEY (video_id) REFERENCES videos (id)
```

| the clause | what it says |
|---|---|
| `KEY` | which columns identify one row of this edge |
| `SOURCE KEY … REFERENCES` | where the arrow starts — a viewer |
| `DESTINATION KEY … REFERENCES` | where it lands — a video |

That is the whole vocabulary. The `watched` table already existed; three
clauses turned it into an arrow. Its other columns (`watched_ms`,
`drop_ms`, `completed`) come along automatically — that is how retention
ends up living on the relationship. `published` and `about`, right above it,
are the same three clauses.

### Build it — one button

👉🌐 In Vibe Studio, open the **World** tab (top left, next to State):

![The World tab, before anything is loaded](codelab-img/s4-world-empty.png)

👉🌐 Press **Build + read the graph ▸**. The grey caption names what the
button runs — `bash scripts/graph.sh` — and that script is three verbs in
order: **CONNECT + LOAD** (dataset + vendor pack + the DDL you just read) ·
**STORE** (your own rows enter the world) · **READ** (the questions).

Its output streams into the page while it works, ~40 seconds:

![The graph being built — step 1 solid, output arriving live](codelab-img/s4-world-running.png)

👀 Nothing here is animated for show: a dot goes solid when the script
actually printed that banner, exactly like the workflow map. The app never
touches BigQuery itself — it runs the same command you could run in tab 1
and tails the log.

When the third dot lands, the readings are underneath it:

![The three readings, straight out of your project](codelab-img/s4-world-done.png)

👀 Those are YOUR videos and YOUR panel's real rows — and the
`engine` chip on each reading is the honest part: `graph#1` ran as **sql**
(one hop needs no graph), `graph#2` and `graph#3` ran as **gql** (two and
three hops). Remember that median drop just before the 5-second mark: the
Memory Bank chapter 🧠 turns it into a rule.

### See it drawn

👉🌐 Open the BigQuery console (just browse): your project → dataset
`vibestudio` → **Tables** shows all six with row counts — then
**Graphs → taste_graph**:

![Your edges, drawn — 4 nodes, 3 edges in the console's graph editor](codelab-img/s4-console-graph.png)

### Watch the agent use it — right now

👉🌐 Nothing to configure — the `read_graph` research node was already wired
to this dataset. Prove it in the app, click by click (the hint box may stay
empty; you type nothing):

1. Open Vibe Studio (Web Preview → 4600) → the **Now** tab.
2. Press **Start next lap ▸** and wait ~20 s while the four research nodes
   run — watch them light up on the map.
3. The form appears, already pre-filled from `user:prefs` (the 💾 chapter's
   edit at work) — press **Resume ▸**:

![Step 4 — the form arrives pre-filled; just press Resume](codelab-img/s3-prefilled-form.png)

4. The **Script ready** card appears. Read its **EVIDENCE** row — a
   `graph#1` chip, highlighted:

![Step 5 — the EVIDENCE row cites graph#1. No memory chips yet — the Memory Bank chapter wires that.](codelab-img/s4-evidence-graph.png)

   Your agent just cited, by name, a reading from the graph you built two
   minutes ago. You never asked it anything: the research step queries the
   graph on every lap, automatically.
5. Finish the lap: press **Render ▸**, wait for the thumbnail card, press
   **Approve**, then press **Finish ▸** — the Memory Bank chapter 🧠 wants
   this lap's audience data anyway.

*What you learned:* a graph is a declared lens over tables you already
have; readings carry names — and you watched your agent cite one without
being asked.

<aside class="positive">
<b>What the next video does differently:</b> the brief cites the
audience's real numbers — <code>graph#1</code> is a chip on the Script
card, not a hope in a prompt.
</aside>

### Read more (optional)

<aside class="positive">
<b>The same thing from the terminal.</b> The button is only a wrapper. In
tab 1: <code>bash scripts/graph.sh</code> prints the same three banners, and
the three verbs are three files you can run one at a time —
<code>python -m bqgraph.load</code> · <code>bqgraph.export</code> ·
<code>bqgraph.report</code>. <code>report</code> also writes
<code>runs/graph_report.json</code>, which is what the World tab renders.
</aside>

<aside class="positive">
<b>What the DDL leaves out on purpose.</b> An edge can also carry
<code>LABEL x PROPERTIES (a, b, c)</code>. Both are optional and this lab
omits both: with no <code>PROPERTIES</code> list every column of the table
is a property (that is why <code>w.completed</code> works in the queries),
and with no <code>LABEL</code> the alias is the label. Three clauses is the
smallest true version.
</aside>

<aside class="positive">
<b>The client is two lines, and the auth ladder in one breath.</b>
<code>_bq()</code> in <code>bqgraph/queries.py</code> is just
<code>bigquery.Client()</code> — no key file, no connection string. Cloud
Shell → ADC is already there (what you're using). Laptop → one command,
<code>gcloud auth application-default login</code>. CI → workload identity.
Nowhere in this lab does a service-account key file appear — that rung is
deliberately skipped.
</aside>

<aside class="positive">
<b>GQL and its SQL twin.</b> Every path question in
<code>bqgraph/queries.py</code> exists twice: a GQL <code>MATCH</code> and a
same-shape SQL join. The <code>engine:</code> tag in the report tells you
which one ran — and reading the two side by side IS the argument for the
graph: the MATCH looks like the question; the join pyramid looks like work.
</aside>

<aside class="positive">
<b>A privacy floor, built in.</b> The queries only surface cohorts of at
least <code>K_ANON</code> viewers (2 in this tiny world; a real platform
uses ~10+), and no query ever returns viewer ids. Aggregates about YOU,
never rows about THEM.
</aside>

<aside class="negative">
<b>The TODO guard.</b> In the shipped starter every edge is already in
place. If an edge is ever carved out (authoring mode), stage 1/3 refuses
loudly with <code>NotImplementedError: TODO: EDGE_TABLE</code> rather than
creating a graph with missing edges — a graph with no watch data would let
every later chapter silently lie.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1: <code>python -m checks.check graph</code>. It asserts that taste_graph exists in your project, your rows joined in, and a path query about YOU returns real rows. Nothing later depends on running this.
</aside>

## 🧠 The channel learns lessons — Memory Bank: connect, write, read
Duration: 0:10:00

![Memory Bank — the write and the read](codelab-img/d9-memory.png)

👀 What the picture shows: the bank sits in the middle with its scope and
its three topics. The left lane is the WRITE — raw readings get distilled
into sentences (never transcripts, never ids), and one `generate` call
files them; consolidation curates (CREATED / UPDATED). The right lane is
the READ — a question, not a key, retrieves the note by similarity, inside
the `read_memory` research node, before any decision is made. Write after
the audience; read at the start of every lap.

**Improvement #3 — the last feed, and the loop closes.** `read_memory` has
run empty since stage 1. This chapter gives it a bank to read: the
audience's numbers become distilled rules, and your channel's **third
video** obeys a lesson nobody typed into a prompt.

- **The layer** — the channel's lessons: a managed **Memory Bank**, hosted on an Agent Engine resource in your project.
- **Why this layer** — lessons must outlive runs, sessions, and this machine — and consolidation (merging new lessons into old ones) is a service, not a file.
- **How it connects** — one command creates the resource; `runs/memorybank.json` caches its address.
- **How the agent uses it** — you write notes with one call, then wire ONE line — and watch the next pitch change because of it.

### Connect: create the bank

👉💻 In **tab 1**, open `memory.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/agent/memory.py
```

👉📖 In `memory.py` — read only, nothing to change — two spots, one idea
each:

- `_bank_config()` — the bank's configuration. The nesting is the concept:
  `AgentEngineConfig → context_spec → memory_bank_config → memory_topics`.
  An Agent Engine becomes a Memory Bank host by carrying this block, and
  **`memory_topics`** define what a note may be about.
- `engine_name(create=True)` — one `agent_engines.create(config=…)` call;
  the resource name it returns is cached to `runs/memorybank.json`.
  **That file is the connection** — every write and read below addresses
  that one name.

<aside class="positive">
<b>Topics: this lab's three, and Google's four.</b> This lab defines three
<b>custom topics</b> — <code>CHANNEL_LESSONS</code> ·
<code>CHANNEL_CONSTRAINTS</code> · <code>AUDIENCE</code>, each with a
one-line description the consolidator reads — mirroring exactly the
<code>[TOPIC]</code> prefixes the learner writes. For common cases Google
ships <b>managed topics</b>: <code>USER_PREFERENCES</code>,
<code>USER_PERSONAL_INFO</code>, <code>KEY_CONVERSATION_DETAILS</code>,
<code>EXPLICIT_INSTRUCTIONS</code>.
</aside>

👉💻 Create it (tab 1 · ~30 s · one-time):

```console
cd ~/vibe-studio-lab
source .venv/bin/activate
python -m agent.bank
```

*You should see:*

```
no Memory Bank yet - creating an Agent Engine to host it (~30s, one-time)…
── created ──
  projects/680476413759/locations/us-central1/reasoningEngines/3403957707466604544
scope for every note: app_name=vibestudio · user_id=creator
memory topics (custom): CHANNEL_LESSONS · CHANNEL_CONSTRAINTS · AUDIENCE
the bank holds 0 note(s)
```

👉🌐 See it in the Cloud console (just browse): **Agent Platform → Memory
Bank** — your engine in the list, with its memory count:

![The bank, in the console — a managed resource in your project](codelab-img/s5-console-memorybank.png)

### Write: distill readings into notes

👀 Two kinds of knowing, and why the graph alone is not enough:

| | BigQuery graph (🌍) | Memory Bank (this chapter) |
|---|---|---|
| holds | the world's raw rows | distilled sentences |
| you get it by | asking a question you know | similarity — the question finds the note |
| lands in | a report you read | the agent's context, mid-decision |

👉💻 In **tab 1**, open `learn.py` in the Cloud Shell Editor by running:

```console
cloudshell edit ~/vibe-studio-lab/agent/learn.py
```

👉📖 In `learn.py` — read only, nothing to change — find `distill()`. The
code is deliberately plain: the drop-at-5s *reading* becomes a
conclusion-first *rule*; the neighbor overlap becomes one audience sentence.
Notice what never enters a note: no video ids, no row counts, no job ids.
👉 In `write_facts()` (same file as before, `agent/memory.py`), the
following call is the entire write path:

<!-- code: GENERATE -->
```python
    op = _cli().agent_engines.memories.generate(
        name=name,
        direct_memories_source=vt.GenerateMemoriesRequestDirectMemoriesSource(
            direct_memories=[{"fact": f} for f in facts]),
        scope=SCOPE, config={"wait_for_completion": True})
```

Three vocabulary words: **`direct_memories_source`** (distilled facts, never
transcripts) · **`scope`** (this app + this user) · **`wait_for_completion`**
(block until **consolidation** finishes, so the response carries per-memory
action flags). `name` is the resource you just created.

👉🌐 Now write the notes — one button, click by click (you type nothing):

1. Open the **Now** tab. The lap you finished in the graph chapter 🌍 is
   still on screen — and the left button is the one you want:

![Step 1 — the published card carries the Learn button](codelab-img/s2c-published.png)

2. Press **Learn from the audience ▸** (the grey caption under it says
   exactly what it runs: `python -m agent.learn, as a button`). It is NOT a
   deploy — it is the after-audience job you would cron nightly, and its
   `main()` is three moves you have already read:

```python
    from bqgraph import export as bq_export
    bq_export.main()          # re-align rows (the graph chapter's stage 2/3)

    facts = distill()         # readings -> notes (the code above)
    ...
    flags = memory.write_facts(facts)   # the generate call you just read
```

3. Wait ~30 seconds, then open the **State** tab: the Memory Bank row —
   the bottom rung of the ladder — now holds the distilled notes:

![Step 3 — the bottom rung is no longer empty](codelab-img/s3-state.png)

### Read: one line, and the agent uses it

👀 The bank is now full — but if you started a lap right now, the EVIDENCE
row would show `graph#N` chips and **no `memory#`**, exactly like the graph
chapter's lap. `read_memory` still says `facts = []`: notes are being written and
never read, so nothing the agent decides can change. This edit is the whole
point of Act III:

👉💻 In **tab 1**, open `graph.py` in the Cloud Shell Editor one last
time by running:

```console
cloudshell edit ~/vibe-studio-lab/agent/graph.py
```

👉✏️ In `graph.py`, locate `read_memory`, **delete** the `facts = []` line
marked `TODO: RECALL` and **uncomment** the line below it:

```
        facts = memory.recall()
```

👉🌐 Watch the agent use the bank, click by click (you type nothing):

1. **Now** tab → press **Start next lap ▸** and wait ~20 s.
2. Press **Resume ▸** on the pre-filled form, then read the **Script ready**
   card. *Our real run's script* opened on the outcome at second zero —
   because the recalled `CHANNEL_CONSTRAINTS` note says conclusion-first.
   Nothing asked you for that; the graph read it.
3. Read that card's EVIDENCE row:

![The loop, closed — a memory# chip in the evidence row](codelab-img/s5-cited-chips.png)

👉🔬 See the recall happen in the raw events — browse only, no commands, no
typing, five clicks:

1. **Web Preview → Change port → 8000**.
2. If the URL no longer ends with `&userId=creator`, add it back at the very
   end and press Enter.
3. Click the **NEW SESSION ▾** picker.
4. Click the newest `run_…_wf` session — this is the lap you just ran.
5. Scroll the event list to the very TOP. Read events #1–#4:

![The research fan-out, raw — #2 trends, #3 read_memory writing the recalled constraint into state, #4 backcatalog](codelab-img/s5-recalled-prompt.png)

Event **#3** — the small `State: constraints` chip — is `read_memory`
writing the recalled note into state, BETWEEN two other research nodes and
BEFORE any decision was made. Memory read on the way to a decision, not in
a demo.

👉🌐 Finish the lap: press **Resume ▸**, then **Render ▸**, then **Approve**,
then **Finish ▸**.

### Three videos, one channel

👉🌐 Open the **Channel** tab one last time (just browse):

![Three laps side by side — one channel, each video better than the last](codelab-img/s5-channel-3.png)

👀 Three cards, in order: the first video (your taste, typed by hand), the
second (form pre-filled, brief citing the graph), the third (script
opening on the conclusion the audience taught it). **The graph never
changed after the EDGES hole — one edge list, three videos, each better,
because each lap woke up knowing more.** And if Setup joined a room, the
room watched your channel grow too — every Finish premiered there,
silently.

*What you learned:* connect is a resource name, write is one `generate`
call, read is one `recall()` line — and only the read made durable state
change the agent's behavior.

<aside class="positive">
<b>What the next video does differently:</b> the script obeys a rule the
channel learned from its own audience — recalled by similarity, before
any decision, cited as <code>memory#</code>.
</aside>

### Read more (optional)

<aside class="positive">
<b>The write path, by hand — and the flags the button hides.</b> The button
runs <code>python -m agent.learn</code>; type it yourself in tab 1 on any
later lap and it narrates: the row alignment, the three distilled notes,
then <b>consolidation flags</b> — <code>CREATED memory#…</code> for a
genuinely new note, <code>UPDATED</code> when the service merges a new
lesson into an old one instead of piling up duplicates. You write facts;
the service curates them.
</aside>

<aside class="positive">
<b>The read path, by hand.</b> In tab 1:
<code>python -m agent.learn --recall "what should my videos do in the first
seconds?"</code> returns the constraint and the lesson — that is
<code>memories.retrieve</code>, similarity search against the scope. You
asked a QUESTION, not a key. (<code>memories.list</code> is the unranked
ledger Studio's governance view uses — search is for agents, the ledger is
for you.)
</aside>

<aside class="positive">
<b>Three names, one resource.</b> The console says <b>Agent Platform</b>,
the SDK namespace is <code>agent_engines</code>, the resource path says
<code>reasoningEngines</code> — one product renamed twice. Deploying your
AGENT to that platform is a different command (<code>adk deploy
agent_engine</code>) and a different lab; this resource only hosts memory
here.
</aside>

<aside class="positive">
<b>The ADK-native wiring, for production.</b> ADK wraps this same resource
as <code>VertexAiMemoryBankService(project, location, agent_engine_id)</code>
— hand it to the <b>Runner</b> as <code>memory_service</code> (the third
slot beside the <code>session_service</code> from 🪞's Read more), or to
<code>adk web</code> via <code>--memory_service_uri</code>. Raw SDK calls in
this lab so you can see the wire; the wrapper in production.
</aside>

<aside class="positive">
<b>Correct it like an operator.</b>
<code>python -m agent.learn --forget &lt;id&gt;</code> deletes a wrong
lesson; <code>--inject "[CHANNEL_CONSTRAINTS] …"</code> hand-writes one. A
memory you can list, delete, and inject is a memory you can govern.
</aside>

<aside class="positive">
<b>Optional check — run it only if you want proof.</b> In tab 1:
<code>python -m checks.check channel</code>. It asserts the notes exist and
are clean (no ids or row counts leaked in), this lap CITED a memory that
really exists, obeyed the conclusion-first rule, and arrived pre-filled
from user:prefs. Nothing later depends on running this.
</aside>

## 🎉 Congratulations
Duration: 0:02:00

You ran a channel: one face, three videos, each better than the last —
with three one-line edits. The point was never typing: it was seeing
exactly where every pause and every byte lives. The whole story in one
table:

| the story beat | the idea to keep |
|---|---|
| ⏳ you made your face | pending is a **value** in the session log, not a thread — and every wait ends with someone answering by id: **human in the loop is the first delivery mechanism** |
| 🪞 you changed it without re-describing it | multi-turn is stable because **agent state has an address outside the process** — a callback wrote `user:avatar`, and the world kept its own ledger |
| 🔀 you ran the channel as one prompt, then grew the graph | "why a workflow" is a before/after you can feel: parallelism you can see, a pause nothing can talk past, a refusal that is an **edge**, not a hope |
| 🗺️ you wrote the edges and ran the lap | the small apps WERE the real graph — the EDGES hole was a recital; a form is a **schema riding an interrupt** |
| 🏁 you pressed once | "all done" is **your two lines** (ADK counts nothing for you); the gates you bench-tested judged real traffic; one press published to your wall — and the room, silently |
| 💾 the channel remembers you | lifetime = **where you store it**; the `user:` prefix moves a key one rung up, and the form filled itself |
| 🌍 the channel reads its audience | a graph is a **declared lens** over tables; readings carry names so briefs can cite them |
| 🧠 the channel learns lessons | write **distilled notes**, read by **similarity** — writes without reads are a diary; the third script obeyed a rule the audience taught |

What this lab was, named precisely: **a long-running agent that learns
from its audience.** Not self-learning — no weights moved, no prompt
rewrote itself, the graph never changed after your edge list, and the loop
runs through humans on purpose (you approve, you press Learn, and turning
an outcome into a rule stays judgment work). The improvement channel is
STATE: same graph + richer state = better video, lap after lap, with no
process alive in between. **The thing that evolves is the state, not the
process.**

And the one law that carried everything: **a long-running agent is defined
by where its state lives, because its process is allowed to die.**

### Read more (optional)

Where to go next — each is one seam in code you already read: real **Veo**
inside `render_submit` · results by **webhook** (the same `answer()` call,
over HTTP) · a **measures graph** beside `taste_graph` ·
**VertexAiSessionService** + **VertexAiMemoryBankService** for the cloud
rungs.
