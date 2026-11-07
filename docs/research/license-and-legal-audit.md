# License and legal audit

Checked **2026-11-07**. This is an evidence record of the third-party code, quoted text, papers, datasets, benchmarks and names this repository includes or cites. It is not a law-firm opinion, a trademark clearance, or permission to copy anything later.

AIC's original material is under Apache-2.0. Cited papers, websites, trademarks and unbundled tools keep their own terms. A public page, a preprint, or a repository license does not relicense a different file.

## Result

No redistributed incompatible code, font, paper PDF, dataset, prompt or article excerpt was found. Eight-word sequences from the pinned skill-creator guide, Agent Skills specification, Agent Skills governance file and basic skill template do not appear in AIC text. Ten-word overlap with the fetched Anthropic multi-agent article is the author list only.

The defects are attribution accuracy, not a copied incompatible work:

1. `LICENSE` and `skills/aic/LICENSE.txt` are byte-for-byte Anthropic's skill-creator license, including the appendix line `Copyright 2026 Anthropic, PBC`. That line is easy to misread as ownership of AIC. Both NOTICE copies now say it is the retained file, not a claim that Anthropic owns or endorses AIC-original material. This audit did not edit `LICENSE`.
2. NOTICE called pip-audit's copyright holder "Python Packaging Authority contributors." The 2.10.1 license file has no copyright line. NOTICE now names the metadata authors and the project's own maintainer statement.
3. The MCP wheels' license copyright is Anthropic, PBC, while PyPI's author field names the Linux Foundation MCP series. NOTICE now states both.

`skills/aic/NOTICE` is distributed inside the skill directory and was updated to the same text as the root `NOTICE`. Leaving the packaged copy stale would drop the corrected attribution.

Everything below that is incompatible stays out of the tree. Do not add it in a later change without a new, file-specific review.

## How this was checked

Licenses were read from the pinned revision, wheel or policy page named below. PyPI wheels for `mcp`, `mcp-types`, `hatchling` and `pip-audit` were unpacked and their license files read. arXiv HTML license badges and Crossref license URLs were read for the versions named in the research ledger. Overlap checks compared word sequences; they do not prove that a close paraphrase is original. Paper statistics in the research ledger were not re-measured.

## AIC's own grant

| Item | What was read | Apache-2.0 relationship |
| --- | --- | --- |
| Root `LICENSE` and `skills/aic/LICENSE.txt` | Byte-identical to [skill-creator `LICENSE.txt`](https://github.com/anthropics/skills/blob/ca45fc496a3436251f191354091d557da31c15b5/skills/skill-creator/LICENSE.txt) at `ca45fc496a3436251f191354091d557da31c15b5`. SHA-256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`. Standard Apache-2.0 terms, then an appendix whose copyright line is `Copyright 2026 Anthropic, PBC`. | The terms in sections 1–9 are Apache-2.0. The appendix is the "how to apply" example and is not one of those sections. Retaining Anthropic's notice is required for that file. Using the filled-in appendix as the only copyright line on AIC's license file is the ambiguity in finding 1. |
| Root `NOTICE` and `skills/aic/NOTICE` | AIC-original copyright: Boom-Vitt and AIC contributors, 2026. | Apache-2.0 section 4(d) is where AIC's own attribution and the retained third-party notices belong. |
| `docs/assets/aic-banner.svg` | Original path wordmark. No embedded font file, third-party logo or upstream image. | AIC-original. |
| Python project metadata | `pyproject.toml` declares `Apache-2.0` and ships `LICENSE` and `NOTICE`. | Consistent with the grant for AIC-original material. It does not relicense dependencies or citations. |

## Anthropic skills repository

Pinned revision `ca45fc496a3436251f191354091d557da31c15b5`. There is no single root `LICENSE`. Licenses differ by skill. AIC does not vendor that repository.

| Path at the pin | License read | In AIC? | If someone copies it |
| --- | --- | --- | --- |
| `skills/skill-creator/LICENSE.txt` | Apache-2.0, appendix copyright 2026 Anthropic, PBC. The file is the one retained as AIC's `LICENSE`. | The license text only. | Compatible. Keep the copyright notice. |
| `template/SKILL.md` | No separate license file. The body is the placeholder description "when Claude should use it" and the heading "Insert instructions below." | Not copied. AIC's `SKILL.md` is a different document. Zero 8-word overlap. | A structural front-matter shape is not that file's text. Do not paste the template body. |
| `skills/skill-creator/SKILL.md` | Covered by the skill-creator Apache-2.0 file. | Not copied. Zero 8-word overlap with AIC text. | Compatible only with the Apache notices kept. |
| `skills/docx`, `skills/pdf`, `skills/pptx`, `skills/xlsx` `LICENSE.txt` (git blob `c55ab42224874608473643de0a85736b7fec0730`) | All rights reserved. Use is governed by Anthropic's consumer or commercial terms. The file prohibits extraction, retaining copies outside the services, derivative works, distribution and sublicensing. | Not present. A repository search found none of these skill names. | Not compatible with Apache-2.0. Do not copy. |
| `skills/frontend-design/LICENSE.txt` (blob `f433b1a53f5b830a205fd2df78e2b34974656c7b`) | Apache-2.0 terms, ending at the end of the terms, without the skill-creator appendix. | Not present. | A different file from skill-creator. Review it again before any reuse. |
| `THIRD_PARTY_NOTICES.md` | Read in full, 405 lines. It attributes imageio 2.37.0 and imageio-ffmpeg 0.6.0 (BSD-2-Clause), FFmpeg 7.0.2 (GPL-3.0), Pillow 11.3.0 (HPND, including a restriction on using Secret Labs AB's or the author's name in advertising), and SIL Open Font License 1.1 fonts. Several fonts have reserved font names, including Erica One, IBM Plex Mono, Italiana, Libre Baskerville and Lora. | Not included. AIC's banner does not embed these fonts. | GPL-3.0 cannot be relicensed under Apache-2.0 only. OFL fonts stay under OFL, and reserved names cannot be used for a modified font. These notices do not pertain to AIC's derivative, so Apache-2.0 section 4(d) does not require them in AIC's NOTICE while the components stay out. |

## Agent Skills standard

Pinned revision `83021e2be457a9b6679148719c1f6074f0ad975e`.

| File | License read | In AIC? |
| --- | --- | --- |
| Repository `LICENSE` | Apache-2.0. Appendix copyright line: `Copyright 2025 Anthropic, PBC`. | Not copied. |
| `skills-ref/LICENSE` | Apache-2.0 terms. | Not copied. |
| `GOVERNANCE.md` | Code and specifications: Apache-2.0. Other documentation: CC BY 4.0. The governance text itself says portions are adapted from Model Context Protocol governance documents under CC BY 4.0. | Not copied. Zero 8-word overlap. |
| `docs/LICENSE` | CC BY 4.0 legal text, read in full. Attribution is required if that documentation is shared. The license does not grant trademark rights. ShareAlike is not part of CC BY 4.0. | Not copied. |
| `docs/specification.mdx` | Specification, therefore the governance file's Apache-2.0 category, not the CC BY docs category. | Not copied. Zero 8-word overlap. AIC implements a skill layout in its own words. |

CC BY 4.0 would require attribution if AIC later shares that documentation or an adaptation of it. Apache-2.0 on the specification does not license the CC BY documents.

## Dependencies AIC declares but does not vendor

These are installed or downloaded separately. Their licenses are not part of AIC's Apache-2.0 grant. MIT and Apache-2.0 are compatible with an Apache-2.0 program when the dependency stays under its own license and, if AIC ever ships a copy, the required notice stays with that copy.

| Package | Version evidence | License file read | NOTICE |
| --- | --- | --- | --- |
| `mcp` and `mcp-types` | Wheels 2.3.0 from PyPI. Both classifiers say MIT. Repository tag `v2.3.0` `LICENSE` matches the wheel text. | MIT. `Copyright (c) 2024 Anthropic, PBC`. PyPI author field: "Model Context Protocol a Series of LF Projects, LLC." | Required only if a copy is shipped. AIC does not vendor the wheels. NOTICE records both the copyright line and the PyPI author. |
| Hatchling | Wheel `hatchling-1.29.0`. | MIT. `Copyright (c) 2021-present Ofek Lev <oss@ofek.dev>`. | Same. NOTICE now includes the email from that line. |
| pip-audit | Wheel and tag `v2.10.1`. Classifier: Apache Software License. | Apache-2.0 terms through "END OF TERMS AND CONDITIONS," with no copyright appendix. `pyproject.toml` authors: Alex Cameron, Dustin Ingram, William Woodruff. README says the project is maintained in part by Trail of Bits with support from Google and is not an official Google or Trail of Bits product. | NOTICE corrected. The code is still not vendored. |
| Gitleaks | Tag `v8.30.1` `LICENSE`, the version CI downloads. | MIT. `Copyright (c) 2019 Zachary Rice`. | Already matched. CI verifies a checksum and does not copy the tool into the skill. |
| `actions/checkout` | Commit `3d3c42e5aac5ba805825da76410c181273ba90b1` (`v7.0.1`). | MIT. `Copyright (c) 2018 GitHub, Inc. and contributors`. | Not shipped in AIC. No NOTICE entry required. |
| `actions/setup-python` | Commit `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (`v7.1.0`). | MIT. `Copyright (c) 2018 GitHub, Inc. and contributors`. | Same. |

Python itself, Git and `gh` are external runtimes. AIC does not vendor them. The PSF license was not re-read because no Python interpreter source is included.

`uv` / `uvx` is named as a user-supplied command. AIC does not pin or vendor it. A sample of tag `0.9.0`, which is not an AIC pin, contains `LICENSE-MIT` (`Copyright (c) 2025 Astral Software Inc.`) and `LICENSE-APACHE` (Apache-2.0 text with the appendix still reading `Copyright [yyyy] [name of copyright owner]`). That sample is not clearance for every uv release.

## Research texts

The ledger in `skills/aic/references/research.md` is citation and original summary. This audit re-read the rights evidence below. It did not re-read every PDF page and it did not treat the ledger's benchmark figures as new measurements.

### Journal and anthology

| Source | Evidence read 2026-11-07 | Compatible with copying into Apache-2.0 AIC files? |
| --- | --- | --- |
| Kim and coauthors, *Capable language models can outgrow the benefits of collaboration*, DOI `10.1038/s42256-026-01268-y` | Crossref: journal-article in Nature Machine Intelligence, issued 2026-07-24, publisher Springer Science and Business Media LLC. License URL for both `tdm` and `vor`: CC BY-NC-ND 4.0, start 2026-07-24. | No. CC BY-NC-ND 4.0, as summarized by arXiv's license guide and by the legal code retrieved the same day, allows unadapted sharing for noncommercial use with attribution. It does not allow sharing adaptations, and it does not allow commercial use. Citation and AIC's own wording can remain. Do not paste prose, figures or tables. |
| Gottweis and coauthors, *Accelerating scientific discovery with Co-Scientist*, DOI `10.1038/s41586-026-10644-y` | Crossref: Nature, issued 2026-05-19. License URL CC BY 4.0. `tdm` starts 2026-05-19. `vor` starts 2026-07-01 (`delay-in-days` 43). Today is after that start. | The license allows reuse with attribution. AIC still does not copy the article. CC BY attribution would be required if a later change shares the article or an adaptation. Third-party material inside the article is not covered by that grant. |
| Wang and coauthors, GroundLM 2026, ACL Anthology `2026.groundlm-1.30` | [ACL copyright FAQ](https://aclanthology.org/faq/copyright/) states that ACL materials from 2016 onward are CC BY 4.0, earlier ACL materials are CC BY-NC-SA 3.0, and third-party materials are excluded. The anthology page for this paper includes that site copyright notice. The PDF's own copyright line was not re-downloaded in this audit. | CC BY 4.0 would allow attributed reuse of the ACL paper. The Microsoft landing page and any `MemoryEffect` code were not licensed by that page. AIC does not copy the paper. |
| Cemri and coauthors, MAST, NeurIPS 2025 | [NeurIPS copyright FAQ](https://neurips.cc/FAQ/Copyright): authors keep copyright and grant NeurIPS a non-exclusive license to copy, distribute and publicly display the paper. That grant is to NeurIPS, not a public Creative Commons license. | No public reuse grant was found. Reference only. |

### arXiv versions

Badges were read from each `https://arxiv.org/html/<id>` page. [arXiv's license guide](https://info.arxiv.org/help/license/index.html) says a Creative Commons choice is the author's public license, while the arXiv.org perpetual non-exclusive license 1.0 gives limited rights to arXiv and limits reuse by others. [API terms](https://info.arxiv.org/help/api/tou.html) put descriptive metadata under CC0 1.0, require one legacy-API request every three seconds on one connection, allow personal or research use of e-print content, and prohibit serving e-prints from another server unless the paper's license allows it. They also prohibit claiming arXiv endorsement. The repository documents that rate limit. This audit did not re-run the collector.

| Version | Badge read | Copy into AIC? |
| --- | --- | --- |
| `2610.17471v1` Cohere coding teams | CC BY 4.0 | Attribution would be required for a copy. Not copied. |
| `2609.38147v1` Meta meta-reasoning | CC BY 4.0 | Same. |
| `2610.16120v1` ScaleMAS | CC BY 4.0 | Same. |
| `2610.10263v1` dynamic concurrency | CC BY 4.0 | Same. |
| `2512.23631v2` BOAD preprint | CC BY 4.0 | Does not license the ICLR PDF. |
| `2601.13295v2` CooperBench preprint | CC BY-SA 4.0 | ShareAlike requires the adaptation's license to be CC BY-SA or a BY-SA compatible license. Apache-2.0 is not that license. Do not merge this text into Apache-2.0 files. The COLM PDF was not given this badge. |
| `2610.36848v1` Evolving Agent Teams | arXiv.org perpetual non-exclusive license | Not a public reuse license. |
| `2603.21489v2` CAID preprint | arXiv.org perpetual non-exclusive license | Not a public reuse license. Not evidence for the COLM PDF. |

COLM 2026 PDFs for CooperBench and CAID, and the ICLR 2026 BOAD PDF, still have no public reuse license verified by this audit. They were not downloaded.

### Engineering articles

The live page `https://www.anthropic.com/research/multi-agent-research-system` was fetched. The HTML has no Creative Commons or article license string. The only copyright string found is the site footer, `© {year} Anthropic PBC`. [Consumer terms](https://www.anthropic.com/legal/consumer-terms), read the same day, are the contract for Claude.ai, Claude Pro and associated services. They are not an open license for research articles. The terms also say Anthropic retains rights in the services.

`https://openai.com/policies/terms-of-use/` returned HTTP 403 to this audit, so OpenAI's current terms were not re-read. No open license is claimed for OpenAI engineering pages or for the other Anthropic engineering articles listed in the ledger.

The dated note `skills/aic/references/research-updates/2026-11-06.md` was compared with the fetched Anthropic article. The only shared 10-word sequence is the author list. That is a credit, not a copied paragraph. The note's figures were not re-measured.

No paper PDF, dataset, benchmark dump, figure or prompt file is in the repository.

## Implementation repositories cited, not included

| Project | What was read | In AIC? |
| --- | --- | --- |
| DeepSeek Harness `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159` | MIT. `Copyright (c) 2026 DeepSeek`. | No code or docs copied. MIT compatibility does not license an associated paper or every file in the repo. |
| EAT `LICENSE` blob `d645695673349e3947e8e5ae42332d0ac3164cd7` | Apache-2.0 text. The appendix copyright line is still the placeholder `Copyright [yyyy] [name of copyright owner]`. The same bytes are the `LICENSE` on commit `b023116a8c3f2b0fe8f21e115e53e3c42381481b` (2026-10-24), which was the latest commit touching that file when checked. | Not copied. The unfilled line means the file does not name a copyright owner. The paper stays under the arXiv non-exclusive license above. |
| BOAD-SWE-Agent `LICENSE` on commit `8b557c8b9a688107151fadbdda5f26b93e7046aa` (2025-12-20), the latest commit touching that file when checked | MIT. It keeps the SWE-agent copyright for John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan and Ofir Press (2024), and a separate 2024 copyright for the BOAD authors named in the file. | Not copied. `main` is not a permanent pin. The ICLR PDF is separate. |
| CAID `f364d9e95727c2e2ba3dbf23f2d6de52c5f3d5fa` | `pyproject.toml` says `license = "MIT"`. The directory listing has no `LICENSE` or `NOTICE` file. | Not copied. A metadata string is not the MIT permission text. Do not copy this revision on that string alone. |
| OpenAI Cookbook `65d3db5684e48c0f18188b509ab8a82feaf55e31` | MIT. `Copyright (c) 2025 OpenAI`. | Not copied. The MIT grant is for that repository, not for every page on the developer site. |
| tmux 3.8 `COPYING` | ISC-style grant. `Copyright (c) Various Authors`. The notice must appear in copies. | Not copied. |
| tmux 3.8 `tmux.1` header | Separate ISC-style grant. `Copyright (c) 2007 Nicholas Marriott`. | The manual is not copied. AIC's profile uses tmux's configuration language. It was not byte-compared with every public `tmux.conf`. |
| oh-my-pi `650f3a108229ee11bf68ba3377f4e8c3391cd424` | MIT. `Copyright (c) 2025 Mario Zechner`, `Copyright (c) 2025-2026 Can Bölük`, `Copyright (c) 2026 Stencil Labs, Inc.` | Not vendored. `docs/maintenance.md` says "Stencil Labs" without "Inc." This audit could not edit that file. The exact line is `Stencil Labs, Inc.` No NOTICE entry is required while no copy is shipped. |

## Names and trademarks

Apache-2.0 section 6 grants no trademark rights. MIT, ISC and CC BY 4.0 do not either.

AIC uses these names to identify a host, a cited source or a recorded check: Claude, Claude Code, Anthropic, OpenAI, Codex, GitHub, Copilot, Cursor, Gemini, Hermes, OpenClaw, Pi, oh-my-pi, omp, Orca, DeepSeek, tmux, and the research institutions named in the ledger. The banner does not use their logos.

Anthropic's consumer terms, for users of those services, say: users may not, without prior written permission, use Anthropic's name, logos or other trademarks in connection with products or services other than the services, or in any way that implies affiliation, endorsement or sponsorship. The contact given there is `marketing@anthropic.com`. Those terms govern use of the services. This audit does not decide whether the clause binds a third party who is only describing compatibility. It does mean AIC must not imply a partnership, must not use Anthropic logos, and must not treat the current descriptive names as a brand license. NOTICE states that limit.

GitHub's terms of service, read the same day, say that use of GitHub's trademarks must follow GitHub's trademark guidelines, including `https://github.com/logos`. This audit did not separately review the logos page. "GitHub Copilot CLI" is used as the product name for a documented skill path.

Brand pages for OpenAI, Cursor, Google Gemini, Nous Research, OpenClaw and Astral were not retrieved. OpenAI's terms URL returned HTTP 403. No logo use was found to compare with those guides.

`https://www.anthropic.com/brand` returned HTTP 404.

## Future promotion, not done here

This audit did not post, star, vote or advertise. The repository has no star-exchange tooling. The README describes the project. The rules below are limits for a later marketing phase.

### GitHub

[Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies), section 4, prohibit spam and inauthentic activity, including fake accounts, automated inauthentic activity, rank abuse such as automated starring or following, secondary markets for that activity, and incentivized inauthentic engagement. Section 10 allows project-related images, links and promotional text in a README or project description. The primary focus of the account must not be advertising. Advertising in other users' accounts, including monetized or excessive bulk content in issues, is prohibited. Promotions must not misrepresent the project, and promotional claims must follow applicable advertising rules, including FTC endorsement guidance. Section 7 says service information must not be used to send unsolicited email.

Practical limit: do not buy stars, trade stars, automate starring, recruit a voting ring, or file promotional issues on other people's repositories. Keep any GitHub description about AIC itself.

### Reddit

The content-policy URL redirected to [Reddit Rules](https://redditinc.com/policies/reddit-rules). Rule 2 requires authentic participation in communities where the person has an interest, and prohibits spam and disruptive behavior, including content manipulation. Rule 5 prohibits deceptive impersonation. Each community's own rules also apply. The page states no numeric self-promotion ratio. The older reddiquette article returned HTTP 403, so this audit does not treat any 9:1 or 10 percent figure as a current Reddit rule.

### Hacker News

[Guidelines](https://news.ycombinator.com/newsguidelines.html), read in full:

- Do not use HN primarily for promotion. Posting one's own work part of the time is allowed; the primary use should be curiosity.
- Do not solicit upvotes, comments or submissions.
- Do not put generated text in posts, and do not automate posting.
- Do not post generated or AI-edited text in comments.
- Do not make titles stand out with uppercase, exclamation points or praise, and do not editorialize a title that is not misleading.

A launch post, if one is ever written, has to be a human-written submission of the actual project, without a vote request and without a manufactured title.

## What was not changed

`LICENSE` and `skills/aic/LICENSE.txt` were not rewritten. Replacing the appendix copyright with Boom-Vitt's copyright, while keeping Anthropic's notice in NOTICE, would remove the ambiguity in finding 1. That edit is outside this change. Tests require those two license files to stay identical to each other.

Research ledger wording, `docs/maintenance.md`, and implementation files were not edited. The Stencil Labs name imprecision and the unverified conference-PDF rights remain recorded here rather than silently "fixed."

No benchmark number in the research ledger was recomputed. Absence of an 8-word or 10-word overlap is not a finding that every sentence is independently phrased in a copyright sense.
