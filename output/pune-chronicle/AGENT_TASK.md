# chronicle-ink: entailment answer (fact-checker)
Read `work/script/entail.request.json` and write `work/script/entail.agent.json`:
```json
{ "schema": "chronicle-entail/1", "script_sha256": "<same as the request>",
  "answers": [{ "id": "S07", "entailed": "yes|partial|no|n/a", "extra_facts": "yes|no", "note": "" }] }
```
- Answer every item id (shots, title, kp<n>, end_card). Items without claims answer `entailed: "n/a"`.
- Judge only from the caption text, the claim texts and the excerpts in the request, not from notes made
  while writing or from memory. When unsure answer `partial` (entailed) and `yes` (extra_facts).
- Notes are at most 280 characters. Then run the same `script` command again.
