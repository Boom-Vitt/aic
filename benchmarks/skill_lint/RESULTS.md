# Skill-lint results

Measured 2026-11-07T19:48:19Z with `python -m benchmarks.skill_lint <checkout> --format json --summary`. The checker is offline and read-only. It does not call a model. No upstream skill text or code was copied into AIC.

The score is AIC's hygiene mean: each skill starts at 100, each error subtracts 20, each warning subtracts 5, and the floor is 0. Format pass means zero errors. Rates are `format_pass / skills`, rounded half up to four decimals. Mean scores are rounded half up to two decimals. Weights and the trigger/terse heuristics are documented in [README.md](README.md); they are not an Anthropic ranking and they do not measure task success.

Specification checked 2026-11-07: [Agent Skills specification](https://agentskills.io/specification), repository [agentskills/agentskills](https://github.com/agentskills/agentskills) revision `83021e2be457a9b6679148719c1f6074f0ad975e`. Anthropic field rules: [skill overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) and [authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices). The Apache-2.0 `skills-ref` demo library was not copied.

## Repositories

Root `LICENSE` files were read at these commits before the trees were linted. Each marker below is present in that file. `anthropics/skills` was not measured: its own README describes a mix of Apache-2.0 skills and source-available document skills (`docx`, `pdf`, `pptx`, `xlsx`), so the tree is not uniformly permissive.

| Repository | Commit | Commit time | License | Skills | Format pass | Errors | Warnings | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [aic](https://github.com/Boom-Vitt/aic) | `a580af9112c3770b046424c82ad15914f909ee4b` | 2026-11-08 01:39:11 +0700 | Apache-2.0 | 1 | 1 (1.0000) | 0 | 1 | 95.00 |
| [obra/superpowers](https://github.com/obra/superpowers) | `22f0b463e7a5e579904dd6211a520321035526f7` | 2026-11-03 14:17:07 -0800 | MIT | 15 | 11 (0.7333) | 14 | 6 | 84.67 |
| [google/skills](https://github.com/google/skills) | `2194d3b8b1f31975fef2f1a0ae6b9ab55bd7ceee` | 2026-11-07 06:41:33 -0800 | Apache-2.0 | 192 | 171 (0.8906) | 80 | 74 | 93.88 |
| [microsoft/skills](https://github.com/microsoft/skills) | `0696600436a9669184ce47e8d8b2ceac62e4bfac` | 2026-11-06 09:55:09 -0800 | MIT | 210 | 180 (0.8571) | 168 | 115 | 89.79 |

AIC's skill tree matches that commit: `git diff --name-only a580af9112c3770b046424c82ad15914f909ee4b -- skills` was empty. The external checkouts are depth-1 clones of those commits. `python -m benchmarks.skill_lint.run_corpus --dest /tmp/aic-skill-lint-corpus` fetches the same pins, checks the license marker again, and prints this summary. GitHub `stargazers_count` at the measurement time was 314032 for obra/superpowers, 23272 for google/skills, and 3183 for microsoft/skills. Those counts are popularity, not hygiene.

Microsoft's 210 skills are regular directories. Forty-eight `.github/skills` entries are symlinks into `.github/plugins` and were not followed; all 48 targets are among the 197 plugin skill directories, and 13 further skills are real directories directly under `.github/skills` (197 + 13 = 210).

## Rules that fired

No repository produced `frontmatter-invalid`, `name-directory`, `description-length`, `secret-pattern`, or `secret-filename`.

| Rule | Severity | AIC | superpowers | google/skills | microsoft/skills |
| --- | --- | ---: | ---: | ---: | ---: |
| `missing-reference` | error | 0 | 9 | 63 | 95 |
| `link-escapes` | error | 0 | 5 | 15 | 70 |
| `field-unknown` | error | 0 | 0 | 1 | 3 |
| `xml-tag` | error | 0 | 0 | 1 | 0 |
| `description-trigger` | warning | 0 | 0 | 3 | 52 |
| `description-person` | warning | 0 | 5 | 16 | 4 |
| `nested-reference` | warning | 1 | 1 | 31 | 44 |
| `skill-line-limit` | warning | 0 | 0 | 5 | 8 |
| `instruction-size` | warning | 0 | 0 | 19 | 7 |

`link-escapes` means the relative path leaves the skill directory. A link to another skill in the same repository still fails, because the specification treats one skill directory as the package. `instruction-size` is `ceil(UTF-8 body bytes / 4)` above 5000, not a model tokenizer count. `description-trigger` is a fixed phrase list (`use when`, `use before`, and the other phrases in the checker), not a judgment by a model.

## Limits

- The frontmatter reader accepts the YAML subset these trees use (mappings, block scalars, plain continuations, quotes, and single-line flow sequences). It matched a string-preserving YAML load on all 418 `SKILL.md` files in this measurement. Other YAML constructs fail closed as `frontmatter-invalid`.
- Directory symlinks are not followed, so alias copies are not scored twice and a symlink farm is not walked.
- Secret detection is pattern-based. It ignores matches that contain placeholder words such as `example` or `redacted`. It can miss credentials and it can flag a documentation string that looks like a live credential without those words.
- Markdown targets that do not look like files (no slash and no short extension) are not treated as references.
