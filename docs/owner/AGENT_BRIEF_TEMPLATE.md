# The agent brief template

Fourteen agents built the Madden 09 module in a day, and every one of their briefs restated the
same rules: the gates, the commit identity, retail-free, which files are shared, what the report
should look like. Those rules are now in `docs/product/MODULE_AGENT_CHARTER.md`, which is in the
repository the agent already has. A brief **references** it and spends its own words on the only
things that differ: the work, the evidence, and the boundaries of this one task.

Keep a brief under roughly 700 words. Everything a brief says that the charter already says is
paid for once per agent, and is one more chance to say it differently.

---

## The template

> **Worktree.** `<absolute path>`, branch `<branch>`. Work only there. Never write outside it.
> Python: `<absolute path to interpreter>` (`export QT_QPA_PLATFORM=offscreen`).
>
> **Standing rules: `docs/product/MODULE_AGENT_CHARTER.md`.** Read it first. It carries the
> gates, the retail-free rule, the shared-file rule, the output discipline, the commit rules and
> the shape of the report. This brief does not repeat them; where it differs from the charter it
> says so and why.
>
> **The task.** `<one paragraph: what to build or answer, on which module, and what "done" is>`
>
> **Already measured — read, do not re-derive.**
> `<the two or three files that answer the questions this task will raise: a disc map, a
> readiness JSON, a measured schema, a registry row. Name them by path.>`
>
> **Boundaries for this task.**
> - Files you may change: `<paths>`. Anything else, stop and report.
> - `<the one or two task-specific prohibitions: an emulator, a machine, a format, a rung>`
>
> **Evidence this task must produce.** `<the specific PASS lines, tokens, counts or artefacts —
> not "prove it works">`
>
> **Report.** The charter's shape. Additionally: `<anything this task needs called out>`

---

## Filling it in

**Worktree.** One agent, one worktree, one branch. Two agents in one tree is a rebase nobody
planned. If the work touches the shared upstream files, say which agent owns that commit — one
of them, not both.

**Already measured.** This is the highest-value paragraph in the brief and the easiest to skip.
Point at the JSON, not the Markdown: the pages are rendered from the records, so the record is
what to quote. The files worth naming are almost always among:

- `docs/owner/scoping/readiness/<SERIAL>.<label>.readiness.json` — how far the shipped readers
  get on that disc, per format family, with the refusals classified;
- `docs/owner/scoping/READINESS_SUMMARY.md` — the fleet in one table, when the task spans discs;
- `docs/owner/disc_maps/<SERIAL>.<label>.map.md` — what is on a disc, container by container;
- `docs/product/measured/<game>/*.json` — a container's schema as measured;
- `mod_editor/games/<game>/pins.json` — what the module ships and claims today.

If the task's first move would be to open a disc image and count something, check whether one of
those files already counted it. Three agents measured the same disc's preload-cache semantics
separately in one day.

**Boundaries.** Two kinds are worth writing down every time, because they are the two that have
gone wrong: *machines* (which host may be touched, and which absolutely may not — an emulator
rig with one headset is not a build machine) and *shared files* (a brief that does not name the
owner of the registry commit gets that commit from three agents at once).

**Evidence.** Ask for the tokens, not for confidence: `MADDEN09_PS2_PLAYBOOKS_VALIDATION_PASS`,
`2K5_MOD_STUDIO_RUNTIME_CLOSURE_PASS`, `PIN AUDIT: CLEAN`, `N of N conformance checks passed`.
An agent that knows which strings it must be able to paste will run the gate that produces them.

## The NAS loop is one line, not a paragraph

Every brief on 2026-09-06 restated the same six instructions for the NAS test loop (rsync, retry
the link, the `.git` marker, the fixtures copy, the script, the summary line). They are now
`tools/owner/integration/nas_loop.sh <worktree> [workers]` on the owner branch; give the agent
that absolute path and say "report its SUMMARY line". The same directory holds
`integrate_gate.sh <worktree>` (every fast gate plus the release gates, PASS token per line),
`resolve_step.py <worktree>` (the mechanical conflict resolver) and `pin_audit.py <worktree>`.

## Choosing the model, which is the launcher's job and not the brief's

Every launch names its model. An agent launched with none inherits the *session's* model, so a
`/model` switch silently changes what an unpinned agent costs; two of eight agents on
2026-09-06 were launched unpinned and spent roughly 800k tokens each against a quota the owner
watches. A `PreToolUse` hook now refuses an unpinned launch, but the hook only enforces that a
choice was made -- making the *right* one is still a judgement:

- **The strongest model available** for cracking an undecoded format, designing a refactor,
  writing a module's writers, research, and anything whose failure mode is a confident wrong
  claim. Most module work is this.
- **A lighter model** for mechanical, fully specified work with a worked example beside it: a
  scripted census, mass validation, a port whose twin is already written.

Say which you chose and why when you report the launch. If the owner names a model, that wins.

## What not to put in a brief

- The gates. They are in the charter, and a brief that lists eight of the nine is worse than one
  that lists none.
- The commit identity recipe. It is in `AGENTS.md` and the charter.
- A restatement of the module's history. Name the one document that holds it.
- A tool's full output as context. Name the file; the agent can read the part it needs.
- Anything retail. A brief is a repository artefact and lives by the same rule as the code.
