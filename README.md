# Content Fact Auditor (free Claude Agent Skill)

Check an AI-drafted article before you publish it. The skill lists **every** checkable claim in the article, separates text that readers cannot see, and labels each claim with an evidence state — so nothing is skipped and "not found" is never reported as "false".

Works in Claude Code, claude.ai (with code execution) and the Claude API. Japanese and English.

## What it does

- **Lists every claim worth checking**, with line numbers and a risk level: prices, hours and dates, quantities, availability ("open", "sold out"), absence ("there is no…", ありません), superlatives ("best", No.1), statistics, first-person experiences, and time-limited wording.
- **Separates hidden text** (HTML comments, `display:none`, `<noscript>`) from what readers see, so a stale price or an old "sold out" notice in a comment is not used as evidence.
- **Compares claims with sources you saved**, conservatively: a number mismatch is only a candidate, and "not found in your sources" is reported as unverified, never as false.
- **Labels each claim** confirmed / reported / unverified / contradicted, and flags first-person experiences that have no record behind them.

The scripts use only the Python standard library, read only the files you give them, and send nothing anywhere.

## Install

**skills CLI**

```bash
npx skills add contentsiteops/content-site-ops
```

**Claude Code (plugin)**

```
/plugin marketplace add contentsiteops/content-site-ops
/plugin install content-site-ops@content-site-ops
```

**Claude Code (manual)**: copy `skills/content-fact-auditor` into `~/.claude/skills/`.

**claude.ai**: zip the `skills/content-fact-auditor` folder and upload it under Settings → Capabilities → Skills (code execution must be on). Menu names can change.

Then ask in your own words, for example: "Fact-check this article against the notes I saved before I publish it."

## Honest limits

- It does not decide truth by itself: you or Claude still open the sources.
- Matching is text-based and can miss contradictions phrased very differently.
- In our own tests, a strong model without the skill also caught the main traps. What the skill adds is full claim coverage and the same auditable report every time.

## Examples

`examples/` has two worked cases (an English article checked against saved source notes, and a Japanese HTML article with a hidden comment) with the scripts' real output.

## More skills for content sites

Search Console drop diagnosis, whole-site boilerplate and template checks, and a release guard for AI-merged pull requests are available as a membership: https://contentsiteops.gumroad.com

## License

MIT. See `LICENSE`.
