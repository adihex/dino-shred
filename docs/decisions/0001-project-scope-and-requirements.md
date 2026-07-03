# ADR 0001: Project scope and requirements — guitar-controlled dino game

**Date:** 2026-07-03 · **Status:** accepted

## Context

Evolve the dino-shred pygame tutorial game into a rhythm trainer controlled by an
electric guitar: each chug makes the dino jump, and the game works like a metronome —
teaching the player to feel the spacing between beats. This is explicitly a
**learning project**: the goal is genuine experience in audio/signal programming in
Python, alongside game development. Every decision gets documented.

## Decisions (from the 2026-07-03 requirements interview)

| Question | Decision | Why |
|---|---|---|
| How does guitar audio reach the Mac? | **M-Audio M-Track Solo** USB interface, guitar DI into the Hi-Z input (channel 2), 48 kHz | Class-compliant (no drivers), clean signal, low latency. Owned already. |
| What triggers a jump? | **V1: any note onset.** Later milestone: spectral filtering so only palm-muted low-string *chugs* count | Staged DSP learning: general onset detection first, then classification. |
| V1 gameplay shape | **Beat-grid mode**: a fixed BPM drives an audible click + visual pulse; obstacles are spawned to arrive at the dino exactly ON beats; every chug is judged (e.g. `−40 ms early`), with streaks | This is the "metronome for guitarists" idea made playable: survive = you kept time. |
| Where does the code live? | **Evolve this repo.** `main.py` game core refactored into a package; original keyboard game preserved | Keeps git history of decisions; existing tutorial notebook becomes chapter 1. |
| How is learning captured? | **Notebook chapter per DSP concept** (with real recordings of the user's guitar plotted/analyzed) **+ this `docs/decisions/` log** | Notebooks for runnable signal intuition; ADRs for architecture rationale. |
| Onset detector authorship | **From scratch in numpy**, staged energy-gate → spectral-flux → chug-classifier; **aubio (git-pinned) as dev-only referee** to benchmark against | Maximum learning; the library never ships in the game path. See ADR 0003. |

## V2 (planned, designed-for but not built in V1)

Select/upload songs (YouTube via yt-dlp, or local files), extract their beat grid
offline, and generate levels from it. Research selected `beat_this` (ISMIR 2024) for
extraction — see `docs/research/2026-07-03-audio-stack-research.md`. The
existing `agentx/apps/music-scanner-service` already covers YouTube search/download
(`yt-dlp`) and could be integrated later; V2 will likely shell out to `yt-dlp`
directly for simplicity.

## Consequences

- The architecture must keep V1 (fixed BPM) and V2 (beat-timestamp list from a song)
  behind one interface — the `Conductor` (ADR 0004).
- Heavy ML dependencies (torch) must stay out of the game runtime (separate uv
  dependency group).
- Success criteria: playable V1 rhythm trainer; user can explain and re-derive every
  DSP component; documented decision trail.
