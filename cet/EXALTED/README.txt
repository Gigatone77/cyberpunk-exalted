EXALTED Terminal 77 — an offline KJV reader for Cyberpunk 2077 (CET mod).

INSTALL
  Extract this zip into the game root. It places
  bin/x64/plugins/cyber_engine_tweaks/mods/EXALTED/

HOTKEYS
  In game: CET Overlay -> Bindings tab -> EXALTED group ->
  bind OPEN EXALTED TERMINAL to your preferred key.

USING IT
  Press your hotkey to show the terminal. To interact (cursor, clicks, and
  all keys below) press the CET Overlay key — CET only hands mouse/keyboard
  to mod UI while the overlay is open.

  KEYS (inside the terminal)
    TAB (or shift-TAB)  cycle the focus panel
      BOOKS    UP / DOWN book, ENTER or RIGHT opens it
      VERSES   UP / DOWN verse, <- -> chapter, PgUp/PgDn 10, HOME/END
      SEARCH   UP / DOWN result, ENTER opens it
      NOTES    UP / DOWN note, ENTER opens it
      MEMORY   SPACE reveal a card, A/H/G/E to grade it
    1..5             jump straight to a tab
    (mouse also works inside the CET overlay; chapter buttons are mouse-only)

  ABOUT tab: dial the glass opacity (how much of Night City shows through).
  BOOK / CH fields in the browse header jump straight to any book/chapter.

DATA
  Fully local, shipped in the mod folder. KJV text (66 books, red-letter
  words of Christ), term index, notes, memory cards, and bookmark live in
  EXALTED/data. Pure Lua — no host process, no network.

CREDITS & LICENSE
  Bible text: KJV 1611/1769, public domain.
  CET/ImGui: MIT. All code here is original. See docs/CREDITS.md.