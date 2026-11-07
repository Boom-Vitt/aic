# Skill-lint results

Measured 2026-11-07T19:59:35Z with `python -m benchmarks.skill_lint <checkout> --format json --summary` on the pinned commits below. The full-rule counts match the 2026-11-07T19:48:19Z run. The checker is offline and read-only. It does not call a model. No upstream skill text or code was copied into AIC.

AIC has **1** skill. obra/superpowers has **15**. google/skills has **192**. microsoft/skills has **210**. A mean over 1 skill is not comparable to a mean over 15, 192, or 210 skills. Nothing in this file says that one repository beats another. The repository tables are alphabetical by upstream name, with AIC last. That order is not a ranking.

Each skill starts at 100. Each error subtracts 20 and each warning subtracts 5, with a floor of 0. **Mean, all rules** averages those scores. **Mean, without AIC-own rules** drops `description-trigger` and `link-escapes` first, then uses the same weights. Both means are rounded half up to two decimals. Format-pass rates are `passes / skill count`, rounded half up to four decimals.

`description-trigger` is AIC's phrase list, not a spec rule. The list includes `use before`. That is the wording in AIC's own description (`skills/aic/SKILL.md`). On these four trees, AIC's skill is the only one whose description matches the list solely because of `use before` (1 skill in AIC, 0 in obra/superpowers, 0 in google/skills, 0 in microsoft/skills). AIC therefore records no `description-trigger` warning. Omitting the rule leaves AIC's mean at 95.00, because the warning was never emitted. The omission does not remove the self-favouring match; it stops the rule from changing anyone's score.

`link-escapes` is also AIC's rule. It flags a relative link that leaves the skill directory, including a link to another skill in the same repository. The Agent Skills specification does not forbid that kind of link. The spec does expect a cited relative file to exist; a missing in-skill file stays `missing-reference` in both means.

Specification checked 2026-11-07: [Agent Skills specification](https://agentskills.io/specification), repository [agentskills/agentskills](https://github.com/agentskills/agentskills) revision `83021e2be457a9b6679148719c1f6074f0ad975e`. Anthropic field and authoring rules: [skill overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) and [authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices). The Apache-2.0 `skills-ref` demo library was not copied. Rule sources are listed in [README.md](README.md).

## Repositories

Root `LICENSE` files were read at these commits before the trees were linted. Each license marker below is present in that file. `anthropics/skills` was not measured: its own README describes a mix of Apache-2.0 skills and source-available document skills (`docx`, `pdf`, `pptx`, `xlsx`), so the tree is not uniformly permissive.

| Repository | Skill count | Commit | Commit time | License | Format pass, all rules | Format pass, without AIC-own rules | Mean, all rules | Mean, without AIC-own rules |
| --- | ---: | --- | --- | --- | --- | --- | ---: | ---: |
| [google/skills](https://github.com/google/skills) | 192 | `2194d3b8b1f31975fef2f1a0ae6b9ab55bd7ceee` | 2026-11-07 06:41:33 -0800 | Apache-2.0 | 171 (0.8906) | 179 (0.9323) | 93.88 | 95.21 |
| [microsoft/skills](https://github.com/microsoft/skills) | 210 | `0696600436a9669184ce47e8d8b2ceac62e4bfac` | 2026-11-06 09:55:09 -0800 | MIT | 180 (0.8571) | 185 (0.8810) | 89.79 | 93.07 |
| [obra/superpowers](https://github.com/obra/superpowers) | 15 | `22f0b463e7a5e579904dd6211a520321035526f7` | 2026-11-03 14:17:07 -0800 | MIT | 11 (0.7333) | 13 (0.8667) | 84.67 | 88.67 |
| [aic](https://github.com/Boom-Vitt/aic) | 1 | `a580af9112c3770b046424c82ad15914f909ee4b` | 2026-11-08 01:39:11 +0700 | Apache-2.0 | 1 (1.0000) | 1 (1.0000) | 95.00 | 95.00 |

AIC's skill tree matches that commit: `git diff --name-only a580af9112c3770b046424c82ad15914f909ee4b -- skills` was empty. The external checkouts are depth-1 clones of those commits. `python -m benchmarks.skill_lint.run_corpus --dest /tmp/aic-skill-lint-corpus` fetches the same pins, checks the license marker again, and prints both means. GitHub `stargazers_count` at 2026-11-07T19:48:19Z was 23272 for google/skills, 3183 for microsoft/skills, and 314032 for obra/superpowers. Those counts are popularity, not hygiene, and they are not comparable to the means above.

Microsoft's skill count of 210 is regular directories. Forty-eight `.github/skills` entries are symlinks into `.github/plugins` and were not followed; all 48 targets are among the 197 plugin skill directories, and 13 further skills are real directories directly under `.github/skills` (197 + 13 = 210).

## Rules that fired

Counts are findings, not skills. Read them next to the skill count in the header. No repository produced `frontmatter-invalid`, `name-directory`, `description-length`, `description-terse`, `secret-pattern`, or `secret-filename`.

| Rule | Source | Severity | google/skills (192 skills) | microsoft/skills (210 skills) | obra/superpowers (15 skills) | aic (1 skill) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `missing-reference` | Spec | error | 63 | 95 | 9 | 0 |
| `field-unknown` | Spec | error | 1 | 3 | 0 | 0 |
| `nested-reference` | Spec guidance | warning | 31 | 44 | 1 | 1 |
| `skill-line-limit` | Spec and Anthropic guidance | warning | 5 | 8 | 0 | 0 |
| `instruction-size` | Spec recommendation, bytes/4 | warning | 19 | 7 | 0 | 0 |
| `xml-tag` | Anthropic | error | 1 | 0 | 0 | 0 |
| `description-person` | Anthropic guidance | warning | 16 | 4 | 5 | 0 |
| `link-escapes` | AIC's own | error | 15 | 70 | 5 | 0 |
| `description-trigger` | AIC's own | warning | 3 | 52 | 0 | 0 |

`instruction-size` is `ceil(UTF-8 body bytes / 4)` above 5000, not a model tokenizer count. Secret checks and the 40-character terse floor are also AIC's own rules; they stay inside both means, and they did not fire on these trees.

## Limits

- The frontmatter reader accepts the YAML subset these trees use (mappings, block scalars, plain continuations, quotes, and single-line flow sequences). It matched a string-preserving YAML load on all 418 `SKILL.md` files in this measurement. Other YAML constructs fail closed as `frontmatter-invalid`.
- Directory symlinks are not followed, so alias copies are not scored twice and a symlink farm is not walked.
- Secret detection is pattern-based. It ignores matches that contain placeholder words such as `example` or `redacted`. It can miss credentials and it can flag a documentation string that looks like a live credential without those words.
- Markdown targets that do not look like files (no slash and no short extension) are not treated as references.
