# Source register

Authority order: signed agreement → implementation documents → supplied frontend.

| # | Source | Version / date | Authority | Status | sha256 (first 16) |
|---|---|---|---|---|---|
| 1 | Marketing As Art and SHOPLNE signed Agreement.pdf (incl. Sched. I SOW, Sched. II fees, 17 Jul proposal appended) | Effective 6 Aug 2026 | Contractual scope | Read in full | c044baeea5854240 |
| 2 | MAA × SHOPLINE — App Architecture & Resilient Inference Plan.pdf | 26 Sep 2026 | Technical: routing, resilience, isolation | Read in full | 9fb9aed7118405ae |
| 3 | MAA SHOPLINE Implementation Blueprint.html | 26-state MVP | Technical: screens, states, open items | Read in full | 88eed7fe3a41c447 |
| 4 | MAA SHOPLINE Technical Kickoff Pack.html | — | Technical: 13 validation items, TD log | Read in full; TD-01..13 all empty | d4f69996db5076fe |
| 5 | MAA SHOPLINE Technical Validation Checklist.html | — | Same 13 items (carried unchanged into #4) | Read (via #4) | c13470127ee84364 |
| 6 | MAA SHOPLINE Product Spec.html | 35 rendered states | Product | Read; superseded on MVP count by #3 | fb05e8b954272f3f |
| 7 | MAA SHOPLINE iOS App UI.html | v3 "The Instrument", 43 screens | Frontend contract (prototype) | Text read; screen code not executed | 3dfd3d538be81b3f |
| 8 | MAA_x_SHOPLINE_IOS APP map.pdf | — | Product narrative | Read | fc031ac145def7b5 |
| 9 | Marketing As Art mobile app design.zip | — | Duplicate bundle of #3–#8 | Listed, not re-read | 0d6b1ebe3c48f86e |
| 10 | Shopline app.txt | 26 Sep | Credentials (NVIDIA, OpenRouter, Groq, SHOPLINE app key/secret) | **Plaintext secrets on disk — see security-audit.md** | b819d230f08b0ed9 |
| 11 | developer.shopline.com — App authorization; Generate and verify signatures; Webhooks overview | fetched 27 Sep 2026 | Public API contract (OAuth, signing, webhook headers) | Implemented; not sandbox-tested | — |

## Supabase project ref
**UNCONFIRMED.** `jojyjjpibkyafbpuungg` vs `j0jyjjpibkyafbpuungg` (letter o vs zero). No Supabase access in this session. The value has no default in code; production refuses to boot until `SHOPLINE_SUPABASE_REF` is set and matches `SUPABASE_URL` / `DATABASE_URL`.

## Conflicts found
- Skill text cites "agreement §7.5" for provider logging. §7.5 is breach notification (2 business days); the logging requirement is derived from it (plan: misrouted prompt = suspected breach). Implemented as derived, labelled so.
- Product Spec (35 states / 22 MVP) vs Blueprint (26 MVP states). Blueprint is later and self-corrects; Blueprint used.
- UI prototype v3 shows 43 screens incl. Brand DNA / Audience / SWOT / Ecosystem onboarding; Blueprint MVP onboarding is 01–05. The plan includes Brand DNA/Audience/SWOT as calibration. **Needs product decision** before those endpoints are built.
- Plan lists Gemini (NLP/embeddings, vision fallback) as "already live and contracted"; no Gemini key or contract is in the supplied sources. Not wired.
