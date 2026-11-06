# Telephony Voice Agent — Master Research Notes (Aug 2026)

Goal: build a production telephony voice agent (Sarvam-grade voices, grounded college answers, village-accent tolerant, provider-failover safe). Sources: research papers, engineering blogs, open-source projects (links at bottom).

---

## 1. The core architecture: the sequential pipeline

The standard architecture behind virtually every production voice agent:

```
Audio In → VAD → STT → LLM → TTS → Audio Out
```

- Each stage is independently testable, swappable, optimizable (no provider lock-in).
- **Streaming at every boundary is non-negotiable.** Streaming STT emits partials while user speaks; streaming LLM sends tokens as generated; streaming TTS starts audio from the first fragment. A non-streaming stage is an immediate disqualifier.
- The alternative: **speech-to-speech (S2S) models** (GPT Realtime, Gemini Live, Groq Voice). Fewer round trips, lower latency, but weaker tool calling and harder interruption handling. Cascaded pipeline still wins on control, compliance, and swappability — right choice for us (we already have a custom brain with tools/KB).

## 2. Open-source stack landscape

| Framework | Language | Mental model | Best fit |
|---|---|---|---|
| **LiveKit Agents** (Apache 2.0) | Python/Node | WebRTC rooms + agent participants | Voice + SIP telephony, multimodal, production-grade turn detection |
| **Pipecat** (Daily) | Python | Pipeline of FrameProcessors (left-to-right data flow) | Phone-first agents, largest provider ecosystem |
| **Ten Framework** | C++ w/ Python bindings | YAML node graph | Sub-300ms latency, edge hardware |
| **Native** (FastAPI + WS) | Python | You write the loop | Zero abstractions, full control — write it when framework abstraction gets in the way |

Reference project to study: `clinic-voice-agent` (Pipecat + LiveKit SIP + Deepgram + Claude + Cartesia).
Architecture: one container per session, SLAs, per-turn JSONL metrics (ASR/LLM/TTS/E2E latency, ASR confidence, tool outcomes) → `/metrics` + `/dashboard`. That tail of observability is exactly what we already want.

**Recommendation: LiveKit Agents (or Pipecat) + LiveKit SIP for the phone path.** LiveKit's SIP handles trunks/numbers; plug Sarvam STT/TTS (official plugin exists), our pipeline as the LLM stage, Silero VAD.

## 3. The latency budget (the make-or-break numbers)

Human conversation turn-taking gap: **200–300ms** (Stivers et al., PNAS, measured across 10 languages). >400ms perceptible slowness; >1.5s flips user's mental model to "query-response". Telephony (PSTN) adds ~500ms across the call path (Cisco measurement) — so the agent software budget is tight.

```
User stops speaking
 ├─ VAD:               ~1ms/frame (Silero) … 50–100ms decision
 ├─ Endpointing (EOU): 100–900ms  ← the biggest controllable lever
 │    fixed-silence: ~500ms dead air per turn
 │    semantic/ML:   ~150–200ms
 ├─ STT finalization:  200–950ms (drive work off *stabilized partials*, not final)
 ├─ LLM TTFT:          100–500ms (Groq-hosted Llama: 50–100ms; GPT-4o-mini: 120–200ms;
 │                     Gemini Flash ~300ms; frontier reasoning: seconds = off the table)
 └─ TTS TTFB:          80–150ms
```

Targets:
- E2E ceiling for a good agent: **600–800ms** (perceived as natural)
- Sub-1s on PSTN = excellent (Cisco ships ~1.3s with trillion-param models via pre-generation)

### What actually moves the needle (in order)
1. **Semantic turn detection** instead of fixed-silence endpointing (cuts EOU 500ms → ~200ms, -45% false interrupts)
2. **LLM TTFT** — pick a fast LLM; streaming; cap response length; keep prompt/context short (TTFT grows with context)
3. **Streaming everywhere**, overlapping stages
4. **Start LLM on stabilized partials** (warm context before turn ends)
5. **Pre-generated first segment** (Cisco trick): prepare the answer's opening while user still speaks → playback starts instantly at EOS; heavier reasoning continues in background, answer continues seamlessly
6. **Region colocation**: agent + STT + TTS + SIP trunk in the same region; never ship audio across continents
7. **Prompt caching**, pre-synthesized hot answers (fees = ideal: pre-render TTS for top questions!)

### Preemptive generation: WARNING for code-switching
ByondLabs (Hinglish production agent): preemptive generation **backfired** for Hinglish — partial transcripts mid-utterance are wrong when speakers switch languages; response generated against wrong partial gets discarded → double generation. **Test before enabling.** For us (Banglish/village), expect the same; start with it off.

## 4. Turn detection for Indic/multilingual callers

- VAD-only = the single biggest source of "the agent is rude" complaints. Fixed 500–700ms silence catches mid-thought pauses.
- Production answer: hybrid — VAD baseline + **semantic turn detector** (LiveKit TurnDetector / MultilingualModel covers 14 languages w/ per-language thresholds) at a *permissive* threshold, then let endpointing timing layer handle the rest.
- Endpointing: `min_delay`/`max_delay`; `dynamic` mode adapts to speaker (fast talkers snappier, slow/village speakers get more patience).
- ByondLabs lessons (Hinglish): ML turn detection + permissive threshold; **disable duration-based interruptions** (a 300ms sound = one short Hindi word, "haan"/"achha"); keep **word-count interrupts (min 2 words)**. False-positive interrupts are far more disruptive than talking over the user half a second.
- Metric to optimize: **false-cut rate vs dead-air rate** — never tune one alone.

## 5. Barge-in / interruption engineering

Requirements for interruption to work at all:
1. **Full-duplex audio** — never mute the mic while the agent speaks (half-duplex = barge-in structurally impossible)
2. **Acoustic echo cancellation (AEC)** so the agent doesn't trigger itself; LiveKit telephony noise-cancellation plugins (BVC) help on PSTN
3. Suppression target: **user-speech-onset → TTS stopped < 200ms**

When a user barges in, three things are in flight. Rules:
- **Cut TTS at a chunk boundary** (stop within one 100–200ms frame, no mid-syllable chop)
- **Truncate model output to what the user actually heard** ("the token the user heard last is the conversational truth") — never stuff the full generated reply into context (agent claims to have said things never heard)
- **Per-tool cancel policy**: read-only lookups (our fee/KB queries) = cancel freely; write/side-effecting ops = complete silently and reconcile on the next turn
- **Reset response state, never conversation state** — the new utterance is a continuation, not a new session
- Distinguish real barge-ins from backchannels ("hmm", "haan"): adaptive interruption (audio model) on cloud, word-count on self-host

## 6. Reliability (matches our provider-failover plan)

- **Failover chains** per capability: STT (Sarvam → Google → Azure), LLM (our chain: Groq → Cerebras → NIM → Gemini → Sarvam-105b), TTS (Bulbul → Google → ElevenLabs)
- **Circuit breakers** per provider: N failures/60s → skip, cooldown, auto-recover
- **LLM hedging**: two LLM calls in parallel, take first usable token — kills P99 lag (P99 is what users call "laggy")
- **Graceful abort contract**: clear audio buffer → abort LLM stream → cancel tool calls → clean history (in that order)
- Workload asymmetry: STT/TTS are out of phase — can co-host; but interruption storms align them → don't co-host STT+TTS on one small box
- **Observability**: per-turn metrics (e2e, LLM TTFT, TTS TTFB) stored + regression-checked; stage traces; transcripts + recordings; provider health telemetry (this is also our college dashboard feed)

## 7. Evaluation

- Measure **TTFT, TTFB, E2E, false-cut rate, dead-air rate** per turn, per provider, per language
- Reuse our golden Banglish/NA/VP test sets as regression harness across provider swaps
- Structural evals from the clinic-agent repo: scripted headless call harness + tool-trace scoring

## 8. Sources (papers / blogs / repos)

- Circle: "clinic-voice-agent" (Pipecat+LiveKit SIP reference) — github nikhilreddy00
- LiveKit blog: sequential-pipeline-architecture, turn-detection-and-interruption-handling, understand-and-improve-agent-latency
- Tian Pan (voice-agent-turn-taking-latency-budget; voice-AI-300ms-budget)
- ByondLabs: Voice Agent Latency: The Sub-Second Tuning Playbook (Hinglish production lessons)
- Cisco/Webex: Building Voice AI That Can Keep Up With Real Conversations (pre-generation, ~1.3s PSTN)
- Twilio: Guide to Core Latency in AI Voice Agents
- Softcery: Lowest-Latency Voice AI Agents (12-component budget)
- Stivers et al. PNAS (human turn-taking 200ms across languages)
- Voice of India benchmark (AI4Bharat + Josh Talks) — STT vendor choice
- Plivo: LiveKit/Pipecat/Ten/native decision matrix + python-agents-examples