# EXALTED Terminal 77 — Credits & Provenance

All code in this distribution is original and authored for this project unless
stated otherwise below. No third-party copyrighted code or data is bundled.

## Bible text
- The **King James Version (Authorized Version)**, 1611 / Oxford 1769 standard
  text — **public domain** (Project Gutenberg eBooks #10 and #10900; Crosswire
  Bible Society / eBible.org). Outside the United Kingdom's printing patent
  (Cambridge/Oxford/Collins), the text is free to use in software.
- No copyrighted modern-spelling or paragraphed edition (e.g. BFBS 1954/2011)
  is used. The embedded text is the public-domain 1769 protocanon (66 books),
  seeded from the desktop EXALTED engine's bundled data.

## Framework / APIs used (no source included)
- **Cyber Engine Tweaks** — MIT licensed
  (github.com/maximegmd/CyberEngineTweaks). Used via its public Lua mod API
  (`registerHotkey`, ImGui bindings, the `mods/` folder contract).
- **Dear ImGui** — MIT licensed (github.com/ocornut/imgui), exposed to mods
  through CET. Used via its API only.

## Original code in this distribution
- CET Lua mod (`init.lua`, `lib/*`, `ui/*`) — original.
- Host bridge (`exalted`, the Go `bridge` subcommand speaking JSON-file IPC) —
  original, built from the desktop **EXALTED Terminal** engine (the same
  author's open project).
- Installer / packaging scripts, docs, and the game-structure zip layout —
  original.

## See also
- `README.md` — install & usage.
- `docs/ARCHITECTURE.md` — IPC contract and layout.
- `docs/NOTES-2026-09-16.md` — build log.