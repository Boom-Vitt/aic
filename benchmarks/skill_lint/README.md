# Skill lint

Offline checker for [Agent Skills](https://agentskills.io/specification) packages. Point it at a skill directory or any repository and it scores every `SKILL.md` it finds. It does not call a model, install a skill, or write into the tree it reads.

```sh
python -m benchmarks.skill_lint path/to/repo
python -m benchmarks.skill_lint path/to/skill --format json --summary
python -m benchmarks.skill_lint.run_corpus --dest /tmp/aic-skill-lint-corpus
```

Run the module from this repository so `benchmarks` is on the Python path. The comparison command clones the pinned repositories under `--dest` and refuses to place them inside this repository.

## What a pass means

A skill **format-passes** when it has zero errors. Warnings do not fail the process; the exit code is 0 for warnings only, 1 when any skill has an error, and 2 when the path cannot be read. A symlinked path is refused rather than followed.

Each skill starts at 100. Each error subtracts 20 and each warning subtracts 5, with a floor of 0. The repository **mean score** is the arithmetic mean of those scores, rounded half up to two decimals. This is AIC's hygiene metric. It is not an Anthropic ranking and it does not measure whether a skill completes tasks.

## Checks

Errors use the Agent Skills specification pinned at `83021e2be457a9b6679148719c1f6074f0ad975e` (checked 2026-11-07) unless a row names Anthropic's skill documents.

| Rule | Severity | Source |
| --- | --- | --- |
| `frontmatter-invalid`, `unreadable`, `undecodable` | error | Spec: YAML frontmatter between `---` lines |
| `field-unknown` | error | Spec: only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` |
| `name-missing`, `name-type`, `name-empty`, `name-length`, `name-case`, `name-hyphen-affix`, `name-consecutive-hyphens`, `name-characters`, `name-directory` | error | Spec: 1–64 character lowercase name matching the directory, NFKC-normalized |
| `name-reserved` | error | Anthropic skill overview: `name` must not contain `anthropic` or `claude` |
| `description-missing`, `description-type`, `description-empty`, `description-length` | error | Spec: non-empty description of at most 1024 characters |
| `xml-tag` | error | Anthropic skill overview: no XML tags in `name` or `description` |
| `license-type`, `compatibility-type`, `compatibility-length`, `metadata-type`, `metadata-value`, `allowed-tools-type` | error | Spec: string license, compatibility of 1–500 characters, string metadata values, string `allowed-tools` |
| `missing-reference`, `link-escapes`, `symlink-reference`, `link-invalid` | error | Spec: relative files inside the skill directory. Symlinks are not followed |
| `secret-pattern`, `secret-filename` | error | AIC: high-confidence credential patterns and sensitive filenames |
| `description-trigger`, `description-terse` | warning | AIC heuristic for the spec's "what it does and when to use it" requirement. Terse means under 40 characters |
| `description-person` | warning | Anthropic authoring guidance: third-person descriptions |
| `skill-line-limit` | warning | Spec and authoring guidance: keep `SKILL.md` under 500 lines |
| `instruction-size` | warning | Spec: instructions under about 5000 tokens. Counted as UTF-8 bytes / 4, not a model tokenizer |
| `empty-body`, `nested-reference`, `absolute-reference`, `file-truncated` | warning | Spec guidance for a body, one-level references, and portable relative paths |

`skills-ref validate` checks frontmatter shape and naming only. This checker is stricter: it also checks links, disclosure size, and secrets. A skill can pass the reference demo library and still fail here.

## Discovery

The walk does not enter directory symlinks, `.git`, `node_modules`, virtual environments, or build outputs. `.github` is included. `SKILL.md` is preferred when `skill.md` is also present. Nested skill directories are scored separately and are not scanned as part of the parent skill. Alias copies that are only symlinks are not double-counted.

## Reproduce the comparison

The pins, licenses, and commands are in [RESULTS.md](RESULTS.md). `run_corpus` fetches those commits, checks that the root license file still contains `MIT License` or `Apache License`, then prints the same JSON summary. It does not copy upstream skill text into this repository.
