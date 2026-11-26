#!/usr/bin/env python3
"""Conservatively match extracted claims against sources the user saved. Never decides labels.

Usage:
  python3 check_against_sources.py --claims claims.json [--sources DIR] [--ledger facts.csv]
                                   [--out-dir DIR] [--max-age-days 90] [--today YYYY-MM-DD]

Inputs
  --claims   claims.json written by extract_claims.py
  --sources  folder of saved source pages as text (.txt / .md / .html). HTML comments and
             hidden elements are read separately: a match found ONLY there is not evidence.
  --ledger   facts ledger CSV with header: claim_key,value,source_url,checked_on
             (checked_on = YYYY-MM-DD). At least one of --sources / --ledger is required.

Candidate states (the model confirms each by reading the cited line):
  contradicted-candidate         a related source passage has a different number of the same kind,
                                 or a source mentions a feature the claim says is absent
  supported-candidate            a related source passage has the same value / statement
  mentioned-needs-reading        the source talks about the subject but the script cannot decide
  not-found-in-provided-sources  nothing related in what was provided. This is NOT "false".
  not-checkable-against-sources  first-person experience: only the writer's own record can support it

Output (in --out-dir, default ./source-check-out): source-check.json, source-check.csv, source-check.md
Standard library only. No network access.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claimlib  # noqa: E402

VERSION = "0.1.0"
LEDGER_COLUMNS = ["claim_key", "value", "source_url", "checked_on"]
SOURCE_EXT = (".txt", ".md", ".markdown", ".html", ".htm")

NEG_EN = re.compile(r"\b(no|not|none|without|unavailable|n't|closed|sold out|discontinued)\b", re.I)
NEG_JA = re.compile(r"(ない|なし|無し|ありません|ございません|不可|非対応|休止|終了|完売|売り切れ)")

DISCLAIMER = (
    "These are CANDIDATES from text matching. Open every cited file:line and confirm before labeling. "
    "'not-found-in-provided-sources' means only that the provided files do not mention it; it is not 'false'. "
    "A saved copy cannot confirm a current state (sold out, open, closed): check the live rendered page.")


def _negated(text):
    return bool(NEG_EN.search(text) or NEG_JA.search(text))


def load_sources(folder):
    """Return list of passages: {file, line, text, folded, tokens, hidden}."""
    if not os.path.isdir(folder):
        raise ValueError("--sources folder not found: %s" % folder)
    passages = []
    files = []
    for root, _, names in os.walk(folder):
        for n in sorted(names):
            if n.lower().endswith(SOURCE_EXT):
                files.append(os.path.join(root, n))
    if not files:
        raise ValueError("--sources folder %s has no .txt/.md/.html files" % folder)
    for path in sorted(files):
        rel = os.path.relpath(path, folder)
        fmt = claimlib.guess_format(path) or "txt"
        blocks, hidden, _ = claimlib.load_document(path, fmt)
        file_fold = claimlib.fold(" ".join(b["text"] for b in blocks)) + " " + claimlib.fold(rel)
        for b in blocks:
            for sent in claimlib.split_sentences(b["text"]):
                passages.append({"file": rel, "line": b["line"], "text": sent, "hidden": False,
                                 "folded": claimlib.fold(sent), "tokens": claimlib.tokens_of(sent),
                                 "file_folded": file_fold})
        for h in hidden:
            passages.append({"file": rel, "line": h["line"], "text": h["text"], "hidden": True,
                             "hidden_kind": h["kind"], "folded": claimlib.fold(h["text"]),
                             "tokens": claimlib.tokens_of(h["text"]), "file_folded": file_fold})
    return passages, len(files)


def load_ledger(path, today, max_age):
    if not os.path.isfile(path):
        raise ValueError("--ledger file not found: %s" % path)
    text = claimlib.read_text_file(path)
    rows = list(csv.DictReader(text.splitlines()))
    if not rows and not text.strip():
        raise ValueError("--ledger %s is empty; expected header %s" % (path, ",".join(LEDGER_COLUMNS)))
    header = [h.strip() for h in (csv.reader(text.splitlines()).__next__())]
    missing = [c for c in LEDGER_COLUMNS if c not in header]
    if missing:
        raise ValueError("--ledger %s is missing column(s) %s; expected header: %s (found: %s)" % (
            path, ", ".join(missing), ",".join(LEDGER_COLUMNS), ",".join(header)))
    out = []
    for i, r in enumerate(rows, start=2):
        key = (r.get("claim_key") or "").strip()
        if not key:
            continue
        item = {"row": i, "claim_key": key, "value": (r.get("value") or "").strip(),
                "source_url": (r.get("source_url") or "").strip(), "checked_on": (r.get("checked_on") or "").strip(),
                "notes": []}
        try:
            d = dt.date.fromisoformat(item["checked_on"])
            age = (today - d).days
            item["age_days"] = age
            if age > max_age:
                item["notes"].append("ledger row %d checked %d days ago (> %d): re-check before relying on it" % (i, age, max_age))
        except ValueError:
            item["notes"].append("ledger row %d: checked_on %r is not YYYY-MM-DD" % (i, item["checked_on"]))
        if not item["source_url"]:
            item["notes"].append("ledger row %d has no source_url" % i)
        item["values"] = claimlib.extract_values(item["value"])
        item["key_folded"] = claimlib.fold(key)
        item["key_tokens"] = [t for t in claimlib.tokens_of(key)] + [w.casefold() for w in re.findall(r"[\u30a1-\u30fa\u30fc\u4e00-\u9fff]{2,}", claimlib.norm(key))]
        out.append(item)
    return out


def _related(claim, p, claim_vals):
    """Decide whether a passage is about the same subject as the claim.

    Related when the source file mentions the claim's entity (if any) and the passage shares
    at least two attribute terms, or one attribute term plus a value of a comparable kind.
    Returns (is_related, matched_terms, passage_values).
    """
    ents = claim.get("entity_terms") or []
    attrs = claim.get("attr_terms") or []
    if ents and not any(e in p["file_folded"] for e in ents):
        return False, [], []
    pvals = claimlib.extract_values(p["text"])
    feats = claim.get("feature_terms") or []
    if "absence" in (claim.get("types") or []) and feats:
        # absence claims are about one feature: any mention of it is related
        hits = [f for f in feats if f in p["folded"]]
        return bool(hits), hits, pvals
    attr_hits = [a for a in attrs if claimlib.text_has_term(p["folded"], p["tokens"], a)]
    ent_hits = [e for e in ents if e in p["folded"]]
    need = min(2, len(attrs))
    has_cmp = any(claimlib.comparable(c, v) or (c["kind"] == v["kind"] == "price" and c.get("unit") is None
                                                and v.get("unit") is None)
                  for c in claim_vals for v in pvals)
    if not attrs:
        ok = bool(ent_hits)
    else:
        ok = len(attr_hits) >= need or (len(attr_hits) >= 1 and has_cmp)
    return ok, attr_hits + ent_hits, pvals


def _same(c, v):
    if c["kind"] == v["kind"] == "price" and c.get("unit") is None and v.get("unit") is None:
        return True  # "free" and "free"
    return claimlib.comparable(c, v) and claimlib.values_match(c, v)


def _compare_values(claim_vals, located):
    """Aggregate over all related passages.

    located: list of (value, "file:line", strong). strong = the passage shares 2+ attribute
    terms with the claim (or is a ledger row). A claim value counts as found if any related
    passage has the same value. The claim becomes a contradicted candidate only when a value is
    found nowhere AND a strongly related passage carries a different value of the same kind.
    """
    verdict = None
    details = []
    for kind in ("price", "time", "date", "percent", "quantity"):
        cv = [v for v in claim_vals if v["kind"] == kind and not v.get("year_only")]
        if not cv:
            continue
        sv = [(v, loc, st) for v, loc, st in located if v["kind"] == kind and any(
            claimlib.comparable(c, v) or _same(c, v) for c in cv)]
        if not sv:
            continue
        found = [c for c in cv if any(_same(c, v) for v, _, _ in sv)]
        missing = [c for c in cv if c not in found]
        if found:
            details.append("%s %s found at %s" % (kind, ", ".join(c["raw"] for c in found), ", ".join(sorted(set(
                loc for v, loc, _ in sv if any(_same(c, v) for c in found))))))
        if missing:
            strong_other = [(v, loc) for v, loc, st in sv if st and not any(_same(c, v) for c in found)]
            if strong_other:
                verdict = "contradicted"
                details.append("%s %s not found; strongly related source values: %s" % (
                    kind, ", ".join(c["raw"] for c in missing), ", ".join("%s (%s)" % (v["raw"], loc) for v, loc in strong_other)))
            else:
                details.append("%s %s not found in related passages (weak match only; read them)" % (
                    kind, ", ".join(c["raw"] for c in missing)))
                if verdict is None:
                    verdict = "unclear"
        elif verdict is None:
            verdict = "supported"
    return verdict, details


def check_claim(claim, passages, ledger):
    types = claim.get("types", [])
    out = {"id": claim["id"], "line": claim.get("line"), "text": claim["text"], "types": types,
           "risk": claim.get("risk"), "evidence": [], "hidden_matches": [], "notes": []}
    if "experience" in types and set(types) <= {"experience", "time_sensitive", "entity_attribute"}:
        out["candidate"] = "not-checkable-against-sources"
        out["notes"].append("first-person experience: sources cannot confirm it; needs the writer's own record "
                            "(date, photo, receipt) or a neutral rewrite")
        return out
    claim_vals = claim.get("values") or claimlib.extract_values(claim["text"])
    if "entity_terms" not in claim or "attr_terms" not in claim:
        claim["entity_terms"], claim["attr_terms"] = claimlib.key_terms(claim["text"])
    attrs = claim.get("attr_terms") or []
    is_absence = "absence" in types and not (claim.get("flags") or {}).get("absence_scoped")
    claim_neg = _negated(claim["text"])
    verdicts = []
    details = []
    located = []
    related_any = False

    for p in passages:
        rel, matched, pvals = _related(claim, p, claim_vals)
        if not rel:
            continue
        loc = "%s:%s" % (p["file"], p["line"])
        if p["hidden"]:
            out["hidden_matches"].append({"file": p["file"], "line": p["line"], "kind": p.get("hidden_kind"),
                                          "text": p["text"][:200]})
            continue
        related_any = True
        ev = {"file": p["file"], "line": p["line"], "text": p["text"][:300], "matched_terms": matched}
        if is_absence:
            if _negated(p["text"]):
                ev["reading"] = "source also states absence/negation"
                verdicts.append("supported")
            else:
                ev["reading"] = "source mentions the feature without negation"
                verdicts.append("contradicted")
        else:
            strong = len([a for a in matched if a in attrs]) >= min(2, len(attrs)) if attrs else True
            located.extend((v, loc, strong) for v in pvals)
            attr_hits = [a for a in matched if a in attrs]
            no_vals = not [v for v in claim_vals if not v.get("year_only")]
            if no_vals and len(attrs) >= 2 and len(attr_hits) >= max(2, 0.8 * len(attrs)) \
                    and _negated(p["text"]) == claim_neg:
                ev["reading"] = "all key terms present (no values to compare)"
                verdicts.append("supported")
        out["evidence"].append(ev)

    for row in ledger:
        cf = claimlib.fold(claim["text"])
        ctoks = claimlib.tokens_of(claim["text"])
        hit = row["key_folded"] in cf or (row["key_tokens"] and all(
            (t in ctoks) if t.isascii() else (t in cf) for t in row["key_tokens"]))
        if not hit:
            continue
        related_any = True
        loc = "ledger:%d" % row["row"]
        ev = {"file": "ledger", "line": row["row"], "text": "%s = %s" % (row["claim_key"], row["value"]),
              "source_url": row["source_url"], "checked_on": row["checked_on"]}
        if row["values"]:
            # a ledger row is one fact: compare it on its own, not pooled with page text
            res, det = _compare_values(claim_vals, [(v, loc, True) for v in row["values"]])
            if res in ("supported", "contradicted"):
                verdicts.append(res)
                ev["reading"] = "; ".join(det)
        elif row["value"] and claimlib.fold(row["value"]) in cf:
            ev["reading"] = "ledger value appears in the claim"
            verdicts.append("supported")
        out["notes"].extend(row["notes"])
        out["evidence"].append(ev)

    if not is_absence:
        res, details = _compare_values(claim_vals, located)
        if res in ("supported", "contradicted"):
            verdicts.append(res)
    out["value_comparison"] = details

    if "contradicted" in verdicts:
        out["candidate"] = "contradicted-candidate"
        if "supported" in verdicts or any("found at" in d for d in details):
            out["notes"].append("some values/passages match and others do not: read all cited lines")
    elif "supported" in verdicts:
        out["candidate"] = "supported-candidate"
    elif related_any:
        out["candidate"] = "mentioned-needs-reading"
    else:
        out["candidate"] = "not-found-in-provided-sources"
        if is_absence:
            out["notes"].append("absence claim: silence in the sources does not prove absence; "
                                "check the places listed in references/verification-by-claim-type.md")
    if out["hidden_matches"] and not out["evidence"]:
        out["notes"].append("matched ONLY hidden text (HTML comment / hidden element): not evidence")
    if "availability" in types and out["candidate"] == "supported-candidate":
        out["notes"].append("state claim: a saved copy is not enough; confirm on the live rendered page")
    return out


def run(claims_path, sources=None, ledger=None, today=None, max_age=90):
    if not os.path.isfile(claims_path):
        raise ValueError("--claims file not found: %s" % claims_path)
    try:
        with open(claims_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError("--claims %s is not valid JSON (%s); pass the claims.json from extract_claims.py" % (claims_path, e))
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ValueError("--claims %s has no 'claims' list; pass the claims.json from extract_claims.py" % claims_path)
    for c in data["claims"]:
        if "id" not in c or "text" not in c:
            raise ValueError("--claims: each claim needs 'id' and 'text' (bad item: %r)" % (c,))
    if not sources and not ledger:
        raise ValueError("give at least one of --sources DIR or --ledger FILE")
    today = today or dt.date.today()
    passages, nfiles = load_sources(sources) if sources else ([], 0)
    rows = load_ledger(ledger, today, max_age) if ledger else []
    results = [check_claim(c, passages, rows) for c in data["claims"]]
    counts = {}
    for r in results:
        counts[r["candidate"]] = counts.get(r["candidate"], 0) + 1
    return {
        "tool": "content-fact-auditor/check_against_sources.py",
        "version": VERSION,
        "claims_file": os.path.basename(claims_path),
        "article": data.get("source_file"),
        "sources_files": nfiles,
        "ledger_rows": len(rows),
        "checked_on": today.isoformat(),
        "disclaimer": DISCLAIMER,
        "counts": counts,
        "results": results,
    }


def write_outputs(res, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "source-check.json")
    cp = os.path.join(out_dir, "source-check.csv")
    mp = os.path.join(out_dir, "source-check.md")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(cp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "line", "candidate", "text", "evidence", "notes"])
        for r in res["results"]:
            w.writerow([r["id"], r["line"], r["candidate"], r["text"],
                        " || ".join("%s:%s %s" % (e["file"], e["line"], e.get("reading", "")) for e in r["evidence"]),
                        " | ".join(r.get("value_comparison", []) + r["notes"])])
    L = ["# Source check: %s" % (res.get("article") or res["claims_file"]), "",
         "> " + res["disclaimer"], "",
         "- Source files: %d, ledger rows: %d, run on %s" % (res["sources_files"], res["ledger_rows"], res["checked_on"])]
    for k in ("contradicted-candidate", "supported-candidate", "mentioned-needs-reading",
              "not-found-in-provided-sources", "not-checkable-against-sources"):
        L.append("- %s: %d" % (k, res["counts"].get(k, 0)))
    L += ["", "| id | candidate | claim | evidence (file:line) | reading / notes |", "|---|---|---|---|---|"]
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    for r in res["results"]:
        ev = "<br>".join("%s:%s" % (e["file"], e["line"]) for e in r["evidence"]) or "-"
        reading = "; ".join(r.get("value_comparison", []) + sorted(set(e.get("reading", "") for e in r["evidence"] if e.get("reading")))
                            + r["notes"]) or "-"
        if r["hidden_matches"]:
            reading += " [hidden-text matches: %s]" % ", ".join("%s:%s" % (h["file"], h["line"]) for h in r["hidden_matches"])
        L.append("| %s | %s | %s | %s | %s |" % (r["id"], r["candidate"], esc(r["text"][:120]), ev, esc(reading[:400])))
    L.append("")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return jp, cp, mp


def main(argv=None):
    ap = argparse.ArgumentParser(description="Match claims against saved sources (candidates only, offline).")
    ap.add_argument("--claims", required=True, help="claims.json from extract_claims.py")
    ap.add_argument("--sources", help="folder of saved source pages (.txt/.md/.html)")
    ap.add_argument("--ledger", help="facts ledger CSV: claim_key,value,source_url,checked_on")
    ap.add_argument("--out-dir", default="source-check-out")
    ap.add_argument("--max-age-days", type=int, default=90, help="ledger rows older than this are flagged (default 90)")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD) for reproducible runs")
    args = ap.parse_args(argv)
    try:
        today = dt.date.fromisoformat(args.today) if args.today else None
    except ValueError:
        print("error: --today must be YYYY-MM-DD, got %r" % args.today, file=sys.stderr)
        return 2
    try:
        res = run(args.claims, args.sources, args.ledger, today, args.max_age_days)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    paths = write_outputs(res, args.out_dir)
    print("Checked %d claims: %s" % (len(res["results"]), ", ".join("%s %d" % kv for kv in sorted(res["counts"].items()))))
    print("Candidates only; confirm each by reading. Wrote %s" % ", ".join(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
