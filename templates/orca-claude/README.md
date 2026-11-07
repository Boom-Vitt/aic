# Orca and Claude Code project

This project uses [AIC](https://github.com/Boom-Vitt/aic) to choose the workflow and [Boom Big Nose Workflow (Orca) v0.4.0](https://github.com/Boom-Vitt/claude-mods-boombignose) to implement it in Claude Code.

Grok Build, Claude Code, and Codex are roles inside Claude Code. A Codex CLI is not required.

## Use it

1. Install Claude Code and link Orca from the AIC repo: `scripts/macos-setup-orca.sh`, then `--apply` on the Mac mini. Sign in by running `claude` yourself.
2. Ask your host to use AIC and draft `.orca/plan.json` from `plan.example.json`. Leave it `draft` until you accept it.
3. Check the plan without a model: `scripts/orca-headless.sh`.
4. Run one bounded session only when you mean to: `scripts/orca-headless.sh --apply`. It uses `dontAsk`, a turn limit, and a wall-clock limit. It does not pass `--bare` and it does not push or delete.
5. Put the project's lint, typecheck, and test command in `gate.sh`. Orca also finds `.orca/gate.sh`. A missing command exits 2.
6. Review in a separate read-only session. Merge and cleanup stay on the Orca plugin scripts and stay dry-run until you pass their apply flags.

Start with one stream. Four agents and six worktrees are ceilings, not a target. On a machine with little free disk, stay at one stream.

## สรุปภาษาไทย

โปรเจกต์นี้ใช้ AIC เลือกวิธีทำงาน และใช้ปลั๊กอิน Orca v0.4.0 กับ Claude Code ชื่อบทบาทไม่ใช่คำสั่งให้ติดตั้ง Codex CLI ค่าเริ่มต้นคือตรวจแผนอย่างเดียว การรัน `claude` ต้องใส่ `--apply` และสคริปต์จะไม่ push หรือลบเวิร์กทรีให้เอง
