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

Each skill starts at 100. Each error subtracts 20 and each warning subtracts 5, with a floor of 0. The repository mean is the arithmetic mean of those per-skill scores, rounded half up to two decimals. The JSON report has two means:

- `mean_score` counts every rule below.
- `mean_score_without_aic_rules` drops `description-trigger` and `link-escapes` before scoring. Those two are AIC's own rules. `format_pass_without_aic_rules` uses the same omission.

AIC's published skill tree contains **1** skill. The pinned comparison trees contain **15** (obra/superpowers), **192** (google/skills), and **210** (microsoft/skills). A mean over 1 skill is not comparable to a mean over 15, 192, or 210 skills. The tables in [RESULTS.md](RESULTS.md) are ordered alphabetically by upstream repository, with AIC last. That order is not a ranking, and no repository beats another.

## Checks

Sources are the Agent Skills specification at `83021e2be457a9b6679148719c1f6074f0ad975e` (checked 2026-11-07), Anthropic's skill overview and authoring guidance, or a rule defined by this checker.

| Rule | Severity | Source |
| --- | --- | --- |
| `frontmatter-invalid`, `unreadable`, `undecodable` | error | Spec: YAML frontmatter between `---` lines |
| `field-unknown` | error | Spec: only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` |
| `name-missing`, `name-type`, `name-empty`, `name-length`, `name-case`, `name-hyphen-affix`, `name-consecutive-hyphens`, `name-characters`, `name-directory` | error | Spec: 1–64 character lowercase name matching the directory, NFKC-normalized |
| `description-missing`, `description-type`, `description-empty`, `description-length` | error | Spec: non-empty description of at most 1024 characters. The spec says the description should state what the skill does and when to use it; it does not require a fixed phrase |
| `license-type`, `compatibility-type`, `compatibility-length`, `metadata-type`, `metadata-value`, `allowed-tools-type` | error | Spec: string license, compatibility of 1–500 characters, string metadata values, string `allowed-tools` |
| `missing-reference`, `symlink-reference`, `link-invalid` | error | Spec: a relative file cited from the skill should exist. Symlinks are not followed |
| `name-reserved` | error | Anthropic skill overview: `name` must not contain `anthropic` or `claude` |
| `xml-tag` | error | Anthropic skill overview: no XML tags in `name` or `description` |
| `description-person` | warning | Anthropic authoring guidance: write descriptions in third person |
| `skill-line-limit` | warning | Spec and Anthropic authoring guidance: keep `SKILL.md` under 500 lines |
| `instruction-size` | warning | Spec: instructions under about 5000 tokens. Counted as UTF-8 bytes / 4, not a model tokenizer |
| `empty-body`, `nested-reference`, `absolute-reference` | warning | Spec guidance: a body, one-level references, and portable relative paths |
| `description-trigger` | warning | AIC's own rule. A fixed phrase list stands in for "when to use it". The list includes `use before`, which is the phrase in AIC's own description. A skill can pass this rule because it copies AIC's wording. That is self-favouring and is not a spec requirement |
| `description-terse` | warning | AIC's own floor: a description under 40 characters is treated as unclear. The spec's minimum is 1 character |
| `link-escapes` | error | AIC's own rule. A relative link that leaves the skill directory is reported. The spec does not forbid a relative link from one skill to another skill in the same repository |
| `secret-pattern`, `secret-filename` | error | AIC's own credential patterns and sensitive filenames |
| `file-truncated` | warning | AIC's own scan cap: only the first 1 MiB of a text file is scanned |

`description-trigger` and `link-escapes` are the two rules removed for `mean_score_without_aic_rules`. Secret checks, the terse-description floor, and `file-truncated` stay in both means.

`skills-ref validate` checks frontmatter shape and naming only. This checker also checks links, disclosure size, and secrets. A skill can pass the reference demo library and still fail here.

## Discovery

The walk does not enter directory symlinks, `.git`, `node_modules`, virtual environments, or build outputs. `.github` is included. `SKILL.md` is preferred when `skill.md` is also present. Nested skill directories are scored separately and are not scanned as part of the parent skill. Alias copies that are only symlinks are not double-counted.

## Reproduce the comparison

The pins, licenses, and commands are in [RESULTS.md](RESULTS.md). `run_corpus` fetches those commits, checks that the root license file still contains `MIT License` or `Apache License`, then prints the same JSON summary. It does not copy upstream skill text into this repository.
