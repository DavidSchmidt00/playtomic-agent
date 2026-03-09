# Backlog

> Work items grouped by epic. For phases and sequencing, see [ROADMAP.md](ROADMAP.md).
> Items are written in problem-first format — understand the pain before the solution.
>
> **Why epics, not user stories?** For a 1–2 person team, stories add ceremony without value.
> Epics answer "what are we actually working on?" at a strategic level. Problem-first write-ups
> answer "why does this matter?" — which is what you need when deciding whether to build at all.

**Status:** 💡 Idea · 📋 Ready · 🔨 In Progress · ✅ Done
**Priority:** P0 (blocking) · P1 (high value, do soon) · P2 (nice to have)
**Effort:** S (< 1 day) · M (1–3 days) · L (1 week) · XL (2+ weeks)

---

## Quick Reference

| Epic | Items | Open |
|---|---|---|
| [Legal & Compliance](#epic-legal--compliance) | LEG-1, LEG-2, LEG-3 | 3 |
| [Operations & Reliability](#epic-operations--reliability) | OPS-1, OPS-2, OPS-3, OPS-4 | 4 |
| [Web Platform](#epic-web-platform) | WEB-1, WEB-2, WEB-4, WEB-5 *(+ WEB-3 completed)* | 4 |
| [WhatsApp Growth](#epic-whatsapp-growth) | WA-2, WA-5, WA-6 *(+ WA-1/3/4 completed)* | 3 |
| [Revenue Loop](#epic-revenue-loop) | MON-0, MON-1, MON-2 | 3 |
| [Contingency Channels](#epic-contingency-channels) | WEB-3, TG-1 | 2 |

---

## Epic: Legal & Compliance

> **Goal:** Be legally compliant before any money changes hands — and before the product grows
> further. GDPR (phone numbers + conversation history are processed today), TMG §5 (Impressum),
> and BGB §§ 312ff (subscription terms) all apply now, not at the point of first payment.

| ID | Title | Priority | Effort | Status | Blocks |
|---|---|---|---|---|---|
| LEG-1 | [Impressum & Datenschutzerklärung](#leg-1--impressum--datenschutzerklrung) | P0 | S | 💡 | LEG-2, MON-2 |
| LEG-2 | [GDPR Data Deletion](#leg-2--gdpr-data-deletion) | P1 | M | 💡 | MON-2 |
| LEG-3 | [Terms of Service / AGB](#leg-3--terms-of-service--agb) | P1 | S | 💡 | MON-2 |

---

### LEG-1 · Impressum & Datenschutzerklärung

**Priority:** P0 · **Effort:** S · **Status:** 💡

**Problem**
The product already processes personal data — phone numbers, conversation history, group
membership — without a published privacy policy or legal notice. GDPR Art. 13 requires
disclosure at the point of data collection. The Impressum obligation (§5 TMG) applies to
any commercially operated website. This risk exists now, not at first payment.

**Why it matters**
Abmahnungen (cease-and-desist letters) for missing legal pages are routine in Germany and can
be issued for any commercial-adjacent website. A Stripe Checkout without a visible Impressum and
privacy policy is a compounded liability.

**Acceptance criteria**
- [ ] `/impressum` exists with: operator name and address, contact email
- [ ] `/datenschutz` exists with: data collected (IP, localStorage, WhatsApp phone numbers),
      legal basis for processing, retention period, user rights (access, deletion, objection),
      contact for data requests
- [ ] Privacy policy covers both the web product and the WhatsApp bot (same data controller)
- [ ] Both pages linked in the website footer
- [ ] Both pages live before any Stripe Checkout link is sent to any group

---

### LEG-2 · GDPR Data Deletion

**Priority:** P1 · **Effort:** M · **Status:** 💡 · **Requires:** LEG-1

**Problem**
Users can request deletion of their personal data under GDPR Art. 17. No mechanism currently
exists to identify and delete all data associated with a phone number (WhatsApp) or browser
profile (web). Group state files contain individual sender data alongside group profiles.

**Why it matters**
This obligation exists now. Complexity escalates when payment data is added in MON-2 — a GDPR
deletion request then also involves Stripe customer records. Easier to build before that exists.

**Acceptance criteria**
- [ ] Admin script or endpoint deletes all data for a given phone number: user file, references
      in group state files, any Stripe customer record
- [ ] Privacy policy (LEG-1) includes instructions for submitting a deletion request
- [ ] Deletion logged with timestamp for proof of compliance
- [ ] Web: users can clear their localStorage profile from the UI

---

### LEG-3 · Terms of Service / AGB

**Priority:** P1 · **Effort:** S · **Status:** 💡 · **Required before:** MON-2

**Problem**
No terms of service exist. Once payment is accepted (MON-2), the operator–customer relationship
is legally unspecified. German consumer contracts for digital services require specific
cancellation and withdrawal provisions (BGB §§ 312ff).

**Why it matters**
A Stripe payment link alone is not a valid subscription agreement under German consumer law.
The Widerrufsrecht must be explicitly addressed — either granted (14 days) or correctly waived
at point of purchase. Without this, every subscription is potentially disputable.

**Acceptance criteria**
- [ ] `/agb` or `/terms` page exists with: service description, pricing and billing cycle,
      cancellation terms, right of withdrawal or compliant digital-service waiver, governing
      law (Germany)
- [ ] Stripe Checkout links to ToS before payment confirmed
- [ ] ToS, Impressum, and Datenschutzerklärung all linked from website footer

---

## Epic: Operations & Reliability

> **Goal:** No silent failures — the operator knows about breakage before users do.
> Silent failures are worse than loud ones: users conclude the product is broken without any
> signal that the team can act on.

| ID | Title | Priority | Effort | Status | Blocks |
|---|---|---|---|---|---|
| OPS-3 | [WhatsApp Connection Alert](#ops-3--whatsapp-connection-alert) | P0 | S | 💡 | — |
| OPS-2 | [Playtomic API Monitoring](#ops-2--playtomic-api-health-monitoring) | P1 | S | 💡 | — |
| OPS-1 | [Cost & Usage Instrumentation](#ops-1--cost--usage-instrumentation) | P1 | S | 💡 | WA-2 |
| OPS-4 | [Non-Blocking Playtomic API Calls](#ops-4--non-blocking-playtomic-api-calls) | P2 | M | 💡 | — |

---

### OPS-3 · WhatsApp Connection Alert

**Priority:** P0 · **Effort:** S · **Status:** 💡

**Problem**
If the WhatsApp account receives a ban warning or is disconnected, there is no alert. A ban
could go undetected for hours. Users see silence and assume the bot is broken. The window to
activate the WEB-3 contingency is wasted.

**Why it matters**
Given documented enforcement escalation since mid-2025, a monitoring gap is a strategic
liability. The entire value of WEB-3 as a contingency depends on knowing about a ban quickly
enough to communicate an alternative to users.

**Acceptance criteria**
- [ ] Alert fires when WhatsApp connection is refused or authentication fails
- [ ] Alert fires on any ban-signal or "unauthorized" response from WhatsApp servers
- [ ] Alert channel configurable (email, webhook, or both) via env var
- [ ] Alert includes reason code and timestamp

---

### OPS-2 · Playtomic API Health Monitoring

**Priority:** P1 · **Effort:** S · **Status:** 💡

**Problem**
The Playtomic API can break silently — returning empty results, changed schemas, or unexpected
errors — with no alert. Users conclude there are no courts available and lose trust, rather than
understanding the agent is broken.

**Why it matters**
Schema drift is detectable before it causes widespread user confusion — but only if something
is watching. Every undetected failure erodes trust in the group context where one visible failure
gets the bot removed.

**Acceptance criteria**
- [ ] API responses validated against expected schema on each call
- [ ] Alert fires when: results unexpectedly empty for a known-good query; schema changes
      (new/missing fields); error rate exceeds threshold
- [ ] Monitoring adds no meaningful latency to normal search responses

---

### OPS-1 · Cost & Usage Instrumentation

**Priority:** P1 · **Effort:** S · **Status:** 💡 · **Required before:** WA-2

**Problem**
Actual cost per conversation — Gemini API tokens, Playtomic API calls, messages sent — is
unknown. The "DMs are cheap (< €0.01)" assumption underpinning WA-2 and the open-DM strategy
is unvalidated.

**Why it matters**
WA-2 should not ship before this is validated. If token costs or usage assumptions are wrong,
the M-2 price point could result in losses. Either outcome undermines the revenue validation goal.

**Acceptance criteria**
- [ ] Gemini API token usage (input + output) logged per conversation
- [ ] Playtomic API call count logged per agent invocation
- [ ] Log query or view shows average cost per DM conversation and per group invocation
- [ ] Logging survives service restarts

### OPS-4 · Non-Blocking Playtomic API Calls

**Priority:** P2 · **Effort:** M · **Status:** 💡

**Problem**
`PlaytomicClient` uses `requests.Session.get()` — synchronous blocking I/O — called directly
from `async def` FastAPI routes. Every Playtomic API call stalls the uvicorn event loop for
its full round-trip duration. The Slot Scanner (`/api/search`) makes up to 14 sequential
blocking calls per request; `/api/clubs` makes one. Under any concurrent load, all other
requests queue behind these blocking calls.

**Why it matters**
Today the service handles low concurrency and the blocking is imperceptible. As usage grows
(especially with the Slot Scanner polling across 14 days), even a handful of concurrent scans
will make the service unresponsive for all users. The fix is incremental — the quick path
unblocks the event loop without touching the client; the correct path removes the blocking
entirely.

**The approach**
Stage 1 (quick, ~1 day): wrap each blocking `PlaytomicClient` call with `asyncio.to_thread()`
in the affected routes (`search_slots`, `search_clubs_endpoint`). The event loop is freed;
requests from other users are processed concurrently.

Stage 2 (correct, ~2 days): replace `requests.Session` in `PlaytomicClient` with
`httpx.AsyncClient`. Routes can then `await` calls directly without the thread-pool overhead.
`httpx` is a drop-in replacement for `requests` and the client API is nearly identical.

**Acceptance criteria**
- [ ] Stage 1: `asyncio.to_thread` wraps all `PlaytomicClient` calls in async routes;
      concurrent requests no longer queue behind a Slot Scanner call
- [ ] Stage 2: `PlaytomicClient` uses `httpx.AsyncClient`; no `asyncio.to_thread` wrappers
      needed; `requests` dependency can be removed
- [ ] All existing API tests pass after each stage
- [ ] Rate-limiting decorators (`@limiter.limit`) added to `/api/clubs` and `/api/search`
      with appropriate per-IP day limits (prerequisite: also add `request: Request` parameter
      required by slowapi)

---

## Epic: Web Platform

> **Goal:** Own the user relationship — persistent identity, cross-device profile, installable app.
>
> WEB-2 is the highest-leverage single item in the backlog. Three reasons: (1) monetization
> prerequisite — server-side profile is the M-1 WTP driver; (2) continuity requirement —
> captures group admin emails before a WhatsApp ban; (3) UX foundation — cross-device profile
> is what solo players would actually pay for. **WEB-1 is not required before WEB-2.**

| ID | Title | Priority | Effort | Status | Notes |
|---|---|---|---|---|---|
| WEB-2 | [User Authentication](#web-2--user-authentication-web) | P1 | L | 💡 | **Start immediately — parallel with WEB-1** |
| WEB-1 | [PWA / Installable App](#web-1--installable-mobile-app-pwa) | P1 | M | 📋 | Parallel with WEB-2 |
| WEB-3 | [Web-Based Group Coordination](#web-3--web-based-group-coordination) | P1 | L | ✅ | Done |
| WEB-4 | [Scanner Presets / Saved Searches](#web-4--scanner-presets--saved-searches) | P2 | S | 💡 | — |
| WEB-5 | [Natural Language → Scanner Form Fill](#web-5--natural-language--scanner-form-fill) | P2 | M | 💡 | — |

---

### WEB-2 · User Authentication (Web)

**Priority:** P1 · **Effort:** L · **Status:** 💡 · **Does not require WEB-1 first**

**Problem**
No user identity exists on the web. Profile is stored in `localStorage`, tied to one browser
on one device. Group admins who pay for a subscription are unreachable if the WhatsApp account
is banned. Solo players lose their profile on browser clear or device switch.

**Why it matters**
Three distinct reasons — all critical:
1. **Monetization prerequisite:** a server-side profile that persists across devices is the
   M-1 WTP driver. "Unlimited searches" or "extended date range" are table stakes. Without
   WEB-2, M-1 has nothing worth paying for.
2. **Continuity requirement:** capturing group admin emails now is the only way to reach paying
   users after a WhatsApp ban. Without WEB-2, a ban destroys the paying customer relationship.
3. **UX foundation:** cross-device profile is the feature solo players would actually pay for.

**Acceptance criteria**
- [ ] Users can sign up / sign in (email magic link or Google OAuth — no passwords)
- [ ] Profile (club, court type, etc.) stored server-side, not in `localStorage`
- [ ] Existing `localStorage` profile migrated on first sign-in
- [ ] Auth state persists across browser sessions
- [ ] Unauthenticated users can still use the free tier — no forced sign-up gate on first visit

---

### WEB-1 · Installable Mobile App (PWA)

**Priority:** P1 · **Effort:** M · **Status:** 📋 · **Parallel with WEB-2**

**Problem**
The web agent requires opening a browser and navigating to a URL. No home-screen icon, no
offline shell, no native feel. Players who would be habitual users never build that habit
because browser URL friction is just high enough to default back to the Playtomic app.

**Why it matters**
Padel is organised on phones, often at short notice. Habit must exist before a paywall can convert. A PWA without auth is still a fancy bookmark — but the install friction reduction is real and improves retention.

**Acceptance criteria**
- [ ] `manifest.json` present with correct app name, icons (192 px and 512 px), theme colour
- [ ] Favicon present and displays correctly in browser tabs
- [ ] Service worker registered, provides at least an offline shell
- [ ] "Add to Home Screen" prompt appears on mobile after first visit
- [ ] Installed app launches in standalone mode (no browser chrome)
- [ ] Lighthouse PWA score ≥ 90

---

### WEB-3 · Web-Based Group Coordination

**Priority:** P1 · **Effort:** L · **Status:** ✅ · **Phase:** M2 (escalates to M0 on ban)

**Problem**
If the WhatsApp account is banned, the native group poll disappears. Telegram is the technically
clean alternative but padel groups in Germany are on WhatsApp — migration has near-zero
conversion (requires every member to install a new app).

**Why it matters**
The coordination mechanic (search → options → vote → booking link) is the product's core value
for the group organiser. If it can only live inside WhatsApp, a ban ends the product.

**The approach**
Organiser asks bot for slots → bot returns `padelagent.de/vote/abc123` → organiser pastes link
into existing WhatsApp group → members tap link, vote on mobile web page → bot sends booking
link when consensus is reached. Users never leave WhatsApp; coordination happens on a page
we control. Works entirely without any WhatsApp integration.

**Acceptance criteria**
- [x] Shareable coordination page generated per search session with slot options
- [x] Members vote without signing in — name + tap is sufficient
- [x] Real-time vote tally visible to all participants on the page
- [x] Consensus triggers webhook that sends booking link to originating chat
- [x] Page mobile-optimised, loads < 2 seconds on 4G
- [x] Complete end-to-end without any WhatsApp integration (web-only flow works)

---

### WEB-4 · Scanner Presets / Saved Searches

**Priority:** P2 · **Effort:** S · **Status:** 💡

**Problem**
Group organisers run the same search week after week (same club, same evenings, same duration).
Filling in the Scanner form from scratch every time is tedious and error-prone.

**Why it matters**
The Scanner's value is speed — it removes the need to describe a search in natural language.
Saved presets remove the last repetitive step. They also increase retention: users who store a
preset have a reason to return to the web app rather than reformulating in chat.

**The approach**
`localStorage` key `padel-agent-scanner-presets` stores `Array<{name, settings}>` where
`settings` captures all form state (club slug/name, date offset, time windows, duration,
court type). A dropdown above the form lists saved presets; a "Save" button prompts for a name
and stores the current configuration.

**Acceptance criteria**
- [ ] "Save preset" button stores the current form state under a user-supplied name
- [ ] Preset selector dropdown populates all form fields on selection
- [ ] Saved presets persist across browser sessions (localStorage)
- [ ] Individual presets can be deleted
- [ ] Up to 10 presets supported; old ones dropped when limit reached

---

### WEB-5 · Natural Language → Scanner Form Fill

**Priority:** P2 · **Effort:** M · **Status:** 💡

**Problem**
The Scanner form is efficient for repeat use but requires deliberate field-by-field input for
first-time or irregular searches. Users who know what they want ("workday evenings 19–21 at
Lemon next 2 weeks") have to translate that into four separate form interactions.

**Why it matters**
This bridges the chat and scanner paradigms: power users get the speed of a structured result
list without losing the convenience of natural language input. It also removes the main
remaining reason to use the chat interface for simple slot searches.

**The approach**
A text field above the Scanner form ("Describe your search…") + parse button. On click,
`POST /api/parse-search` sends `{text, today}` to the backend; the route calls
`llm.invoke()` with a structured JSON extraction prompt (no LangGraph agent needed — one-shot
call). The response is `SearchRequest`-shaped JSON; the frontend populates form state.
Users can review and tweak the pre-filled values before searching.

**Acceptance criteria**
- [ ] `POST /api/parse-search` endpoint extracts club, date range, time windows, duration from
      free-form text; returns partial `SearchRequest` JSON (missing fields left null)
- [ ] Frontend pre-fills form state from the response; user can edit before searching
- [ ] Graceful fallback if parsing fails (show error, keep form editable)
- [ ] Endpoint does not run a full LangGraph agent — direct `llm.invoke()` only
- [ ] Response time < 3 seconds on typical input

---

## Epic: WhatsApp Growth

> **Goal:** Turn DM users into group adopters; turn group users into web users.
> Build the viral loop: DM discovery → group coordination → web identity → paying customer.
>
> Completed in this epic: WA-1 (chunking), WA-3 (media handling), WA-4 (reply context).

| ID | Title | Priority | Effort | Status | Dependency |
|---|---|---|---|---|---|
| WA-2 | [DM → Group & Web Funnel](#wa-2--dm--group--web-funnel) | P1 | M | 📋 | After OPS-1 validates cost |
| WA-5 | [Web URL Surfacing in Groups](#wa-5--web-url-surfacing-in-whatsapp-responses) | P1 | S | 💡 | — |
| WA-6 | [Group Member Sharing Path](#wa-6--group-member-sharing-path) | P1 | S | 💡 | — |

---

### WA-2 · DM → Group & Web Funnel

**Priority:** P1 · **Effort:** M · **Status:** 📋 · **Run after OPS-1**

**Problem**
DM users who find a slot via the bot have no natural path to the group feature or web app.
DM-only usage generates no group virality and no path to revenue.

**Key assumption (unvalidated)**
The barrier to group adoption is *awareness* — DM users don't know the bot works in groups.
If the real barrier is social trust ("I don't want a bot in my group") or permissions (only
admins can add bots), a one-line tip will not convert. Validate by tracking group adoption
rate after WA-2 ships.

**Why it matters**
DMs are the lowest-friction discovery channel. The highest-relevance moment is when a query
signals multi-player coordination context (doubles, group game, friends) — not generically
when any slot is found.

**Acceptance criteria**
- [ ] Slot found + multi-player context → one-line mention that bot works in WhatsApp groups
- [ ] Slot found + solo context → group feature not promoted (irrelevant to this job)
- [ ] First preference saved in DM → one-line mention of padelagent.de for cross-device access
- [ ] Promotion suppressed if same type appeared in immediately preceding bot message
- [ ] Tone genuinely helpful — one line, never a banner or hard sell
- [ ] Group conversations and web completely unaffected
- [ ] `UserState` stores last promotion type shown (needed for suppression logic)

---

### WA-5 · Web URL Surfacing in WhatsApp Responses

**Priority:** P1 · **Effort:** S · **Status:** 💡

**Note:** WA-2 handles DM conversations. WA-5 covers the same mechanic for *group*
conversations — the web URL is the only persistent channel we control if the account is banned.

**Problem**
Group users who experience the bot's value have no natural path to the web product. The URL
is never surfaced during a normal group interaction.

**Why it matters**
The web is the only channel Padel Agent fully controls. Driving group users to it organically —
before a ban — is the primary mechanism for Bet 3 to work. Without this, the web remains
invisible to the users most likely to become paying customers.

**Acceptance criteria**
- [ ] Slot found in group → response includes a brief mention of `padelagent.de`
- [ ] Group preference saved for first time → agent mentions web product
- [ ] Mention is short and non-intrusive — one line max, never in consecutive messages
- [ ] DM conversations unaffected (handled by WA-2)

---

### WA-6 · Group Member Sharing Path

**Priority:** P1 · **Effort:** S · **Status:** 💡

**Problem**
Current acquisition depends entirely on the *organiser* adding the bot. But the organiser who
bypasses coordination ("I'll just pick a time") never feels the pain and will never add it.
Group members who suffer from having no scheduling agency are the ones with the motivation —
but only admins can add bots to groups in most WhatsApp configurations.

**Why it matters**
JTBD analysis: the acquisition moment is immediately after a painful coordination thread, not
in anticipation of one. A member who just lived through a 15-message scheduling nightmare is
primed to share the bot — but that motivation evaporates in minutes without a frictionless path.

**The approach**
DM responses in multi-player context include a shareable `padelagent.de/invite` link — a page
the member pastes into their existing group. One sentence explaining what the bot does + "Add
to your group" CTA. Creates an acquisition path that doesn't require admin buy-in. Connects
to WEB-3: the same shareable link can become the web-based coordination entry point after a ban.

**Acceptance criteria**
- [ ] DM responses in multi-player coordination context include short shareable link alongside
      group feature mention
- [ ] Linked page explains group bot in one sentence, mobile-optimised, loads < 2 seconds
- [ ] Page works without any WhatsApp integration (pure web page)
- [ ] Click-through rate on link tracked (feeds North Star metric)
- [ ] DM-only (solo context) and group conversations unaffected

---

## Epic: Revenue Loop

> **Goal:** First euro in the door — validated price, enforced trial, working payment flow.
>
> **Sequencing is strict.** MON-0 (WTP validation) must complete before MON-2 (payment flow).
> MON-1 (trial counter) can run in parallel with MON-0. The binding risk is not price sensitivity;
> it is whether the organiser will pay *on behalf of the group*. Validate this first.

| ID | Title | Priority | Effort | Status | Dependency |
|---|---|---|---|---|---|
| MON-0 | [Willingness to Pay Validation](#mon-0--willingness-to-pay-validation) | P1 | S | 💡 | — |
| MON-1 | [Group Trial Counter](#mon-1--group-trial-counter) | P1 | S | 💡 | — |
| MON-2 | [Group Payment Link Flow](#mon-2--group-payment-link-flow) | P1 | M | 💡 | MON-0 + MON-1 + LEG-1 + LEG-2 + LEG-3 |

---

### MON-0 · Willingness to Pay Validation

**Priority:** P1 · **Effort:** S · **Status:** 💡 · **Must complete before MON-2**

**Problem**
The €8–12/month M-2 price was set without talking to a single group organiser. The organiser
incentive risk — will they pay on behalf of the group? — is the primary conversion unknown in
the entire revenue model. MON-2 is being designed without any data on whether this number
is right, too high, or too low.

**Why it matters**
Five 15-minute conversations can answer the three questions that determine whether MON-2
succeeds: Will the organiser pay alone, or split with the group? At what price does "yes"
become "maybe"? Is "coordination elimination" the right paywall message?

**Acceptance criteria**
- [ ] 5 group organisers interviewed (in-person, video call, or phone — 15 min each)
- [ ] Each interview arc: describe last coordination thread → how long it took → WTP for a
      tool that eliminated it → fair price → would you pay alone or split with the group?
- [ ] Van Westendorp questions: too cheap to trust / cheap / expensive but worth it / too expensive
- [ ] Findings documented: WTP range, solo-pay vs. split preference, strongest message anchor
- [ ] MON-2 price point and paywall message updated based on findings before implementation
- [ ] If < 3 of 5 organisers say they'd pay ≥ €5/month alone: escalate organiser incentive
      risk before proceeding to MON-2

---

### MON-1 · Group Trial Counter

**Priority:** P1 · **Effort:** S · **Status:** 💡 · **Parallel with MON-0**

**Problem**
No mechanism tracks how many free group polls a group has consumed. Without this, M-2 cannot
be enforced — the trial is indefinite. We either never charge, or impose an abrupt paywall
with no prior warning. Both are bad outcomes.

**Why it matters**
The trial is the intended on-ramp to revenue. A lower threshold (10 polls vs. a higher number)
surfaces willingness to pay faster — the primary unknown in this model.

**Acceptance criteria**
- [ ] Group poll count stored in server-side group state (alongside profile/history)
- [ ] Count increments once per agent invocation in a group — not per message
- [ ] At trial threshold, response includes trial-expiry notice anchored to the job done
      (e.g. "You've organised X games without a scheduling thread"), not usage consumed
- [ ] Trial threshold configurable via env var (default: 10)
- [ ] Counter resets when paid subscription activated
- [ ] Escape hatch prevention: trial tied to both group JID *and* organiser's phone number;
      creating a new group does not grant a new trial to an organiser who already consumed one

---

### MON-2 · Group Payment Link Flow

**Priority:** P1 · **Effort:** M · **Status:** 💡
**Requires:** MON-0 + MON-1 + LEG-1 + LEG-2 + LEG-3

**Problem**
When a group's trial expires, there is no mechanism to convert the organiser into a paying
customer. The bot goes quiet and revenue is lost.

**Why it matters**
This is the only step between a group that has experienced the value and actual revenue. The
flow must be completable on mobile inside WhatsApp — if it requires a laptop, conversion
will be near zero. Test on real devices before shipping.

**Acceptance criteria**
- [ ] Trial expiry message anchored to the coordination job — not search quantity:
      *"You've organised 10 padel games without a single scheduling thread. To keep it that
      way: [payment link]"* — not *"Your free searches are used up."*
- [ ] Payment link is direct Stripe Checkout URL completable on mobile in < 60 seconds —
      **test on real Android and iOS before shipping**
- [ ] Stripe webhook activates group subscription in server-side state
- [ ] Bot resumes normal operation immediately after activation — no redeployment required
- [ ] Subscription status stored persistently in group state file
- [ ] If payment not completed within 7 days: one follow-up reminder, then bot goes quiet

---

## Epic: Contingency Channels

> **Goal:** The core coordination mechanic survives a WhatsApp ban — without asking users
> to change platforms.
>
> ⚠️ **WEB-3 escalation trigger:** If OPS-3 fires a ban signal, WEB-3 immediately moves to M0.
> Prepare the spec now so the move is a deployment decision, not a design session.
> TG-1 is for long-term platform diversification, not an emergency replacement.

| ID | Title | Priority | Effort | Status | Phase |
|---|---|---|---|---|---|
| WEB-3 | [Web-Based Group Coordination](#web-3--web-based-group-coordination) | P1 | L | ✅ | M2 |
| TG-1 | [Telegram Channel](#tg-1--telegram-channel-secondary-contingency) | P2 | L | 💡 | M2 |

*WEB-3 full write-up is in the [Web Platform epic](#epic-web-platform) above.*

---

### TG-1 · Telegram Channel (Secondary Contingency)

**Priority:** P2 · **Effort:** L · **Status:** 💡

**Problem**
If both the WhatsApp account and WEB-3 fail to retain users, a Telegram channel provides a
platform-independent home for the coordination mechanic.

**Honest assessment**
WEB-3 is the better contingency for *existing* WhatsApp groups — it requires no platform switch.
TG-1 is relevant for new user acquisition in communities already on Telegram, and as a
long-term hedge toward platform diversification. Migrating an active padel group from WhatsApp
to Telegram has near-zero conversion in practice.

**Acceptance criteria**
- [ ] Telegram bot registered and deployable from the same agent core (shared tools, profiles)
- [ ] Group search and poll-equivalent flow works in Telegram groups
- [ ] User profile storage is channel-agnostic (same data model, different JID namespace)
- [ ] Both channels can run simultaneously — not a hard migration

---

## Completed

| Item | Notes |
|---|---|
| Group poll + voting flow | Full loop: search → native poll → vote tally → booking link |
| Multi-language support (DE / EN) | Region selector on web; auto-detect on WhatsApp |
| User preference profiles | Web (localStorage) + WhatsApp DM + WhatsApp groups |
| Multi-day slot search | Up to 7 days in a single request on both channels |
| Group join intro message | Sent automatically when bot is added to a group |
| Human-like typing delay | Configurable WPM; visible typing indicator |
| WA-1 · Message Chunking | Long responses split into paragraph chunks; booking link isolated as final message |
| WA-3 · Media Message Handling | Non-text messages receive a friendly German reply; no agent call made |
| WA-4 · Reply/Quote Context | Quoted message text forwarded to agent context; bot-self-quote guard included |
