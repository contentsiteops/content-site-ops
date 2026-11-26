#!/usr/bin/env python3
"""Extract every checkable claim from an article so that none is skipped.

Usage:
  python3 extract_claims.py ARTICLE [--out-dir DIR] [--lang auto|ja|en]
                            [--min-risk low|medium|high] [--format auto|md|html|txt]
                            [--known FILE]

Input: .md / .html / .txt. HTML tags, scripts and styles are stripped. HTML comments and
hidden elements (display:none, hidden, <template>, <noscript>) are NOT treated as article
text: they are reported separately as "hidden text, not visible to readers".

Output (in --out-dir, default ./claims-out):
  claims.json            all claims, hidden text, audit-date markers, counts
  claims.csv             one row per claim (opens in a spreadsheet)
  claims-checklist.md    checklist grouped by risk, for the human / model to work through

Every claim starts with status "unverified". This script never decides true/false.
Standard library only. No network access.
"""

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claimlib  # noqa: E402

VERSION = "0.1.0"
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

TYPE_LABEL = {
    "price": "price / money",
    "time": "time / hours / dates",
    "quantity": "quantity / measurement",
    "availability": "availability / state",
    "absence": "absence / negation",
    "superlative": "superlative / ranking",
    "statistic": "statistic / attribution",
    "experience": "first-person experience",
    "time_sensitive": "time-sensitive",
    "entity_attribute": "named entity + attribute",
}

TIE_ORDER = ["experience", "absence", "availability", "superlative", "statistic", "price",
             "entity_attribute", "time", "quantity", "time_sensitive"]

HINT = {
    "price": "Operator's current price page; note tax, age bands, date. Numbers may be read from a non-JS fetch.",
    "time": "Operator's hours/calendar page incl. holiday and seasonal exceptions; note the date checked.",
    "quantity": "Operator's spec/access page; quantities from maps or reviews are only 'reported'.",
    "availability": "State words (sold out, closed, open now) must be seen on the live rendered page, not a raw fetch.",
    "absence": "Before writing 'none/no': rendered listing, campaign pages, per-location pages, your own other articles.",
    "superlative": "Needs a named, dated ranking source; otherwise remove or rewrite as a neutral description.",
    "statistic": "Trace to the original study/survey (publisher, year, sample). Search snippets are not sources.",
    "experience": "Needs the writer's own record (date, photo, receipt). Without it rewrite as neutral fact.",
    "time_sensitive": "Record the end date and set a re-check date; re-verify before every republish.",
    "entity_attribute": "Entity's own page; identify same-name entities by 2 of address / operator / opening year.",
}

# --------------------------------------------------------------------------
# Rules. Each rule: (type, regex, risk, reason). Patterns run on NFKC-normalized text.
# --------------------------------------------------------------------------

I = re.I

EN_STATE_STRONG = re.compile(
    r"\b(sold out|out of stock|in stock|back in stock|limited stock|open now|now open|"
    r"temporarily closed|permanently closed|closed (?:for|until|temporarily|permanently)|"
    r"discontinued|no longer (?:available|offered|sold|open)|reopen(?:s|ed|ing)?|"
    r"fully booked|booked up|waitlist)\b", I)
EN_STATE = re.compile(
    r"\b(available|unavailable|reservations? (?:are |is )?(?:required|needed|recommended|not needed)|"
    r"booking (?:is )?required|allowed|not allowed|permitted|prohibited|accepts?|accepted|"
    r"can (?:bring|use|rent|borrow|enter|park|buy|book|feed|touch)|cannot|can't|"
    r"wheelchair[- ]accessible|stroller[- ]friendly|open (?:daily|every day|year-round|24 hours))\b", I)
JA_STATE_STRONG = re.compile(
    r"(完売|売り切れ|売切れ|品切れ|在庫(?:あり|なし|切れ|僅少)|販売終了|販売中|発売中|受付終了|受付中|"
    r"営業中|休業中|閉店|閉館(?!時間|日)|閉園(?!時間|日)|閉業|営業終了|再開|リニューアル(?:中|オープン|工事)|"
    r"一時休止|休止中|運休|満席|予約(?:受付)?(?:終了|満了))")
JA_STATE = re.compile(
    r"(できます|できる|できません|できない|可能です|不可|(?<![A-Za-z])OK|(?<![A-Za-z])NG|利用可|使用可|"
    r"予約(?:必須|不要|制|が必要|は不要)|貸し出し(?:あり|なし|可|しています)|貸出(?:あり|なし|可)|"
    r"レンタル(?:可|あり|できます)|持ち込み(?:可|不可|OK|NG|できます|できません)|"
    r"(?<=[\u4e00-\u9fff\u30a1-\u30fa\u30fc）)])\s?(?:あり|有り|なし|無し)(?![がま])|"
    r"年中無休|無休)")

EN_ABSENCE = re.compile(
    r"\b(there (?:is|are) no|there isn't|there aren't|there's no|no [a-z-]+(?: [a-z-]+)? (?:is|are) (?:available|provided|offered)|"
    r"(?:does|do)(?: not|n't) (?:have|offer|provide|sell|allow|accept|serve)|has no|have no|offers no|"
    r"not available|unavailable|lacks?|without (?:a|an|any)|none (?:on site|available)|isn't offered|"
    r"is not offered|are not offered|no longer)\b", I)
JA_ABSENCE = re.compile(
    r"(ありません|ございません|(?:は|が)ない(?:です|ので|ため|。|、|$)|ないです|"
    r"(?<=[\u4e00-\u9fff\u30a1-\u30fa\u30fc）)])\s?(?:なし|無し)(?![がま])|非対応|不可|"
    r"置いていな|置いてな|設置されていな|設置はな|用意されていな|用意はな|取り扱(?:い|って)(?:は)?(?:ありません|ない|していません)|"
    r"見当たらな|見当たりません)")
SCOPED_ABSENCE = re.compile(
    r"(could not find|couldn't find|did not find|didn't find|we found no|no mention|not (?:listed|mentioned|stated|shown) (?:on|in)|"
    r"not confirmed|unconfirmed|we could not confirm|could not confirm|not (?:yet )?verified|"
    r"記載(?:が|は)?(?:ありません|ない|な[かく]|見当たら|見当たり|確認でき)|確認(?:でき|が取れ)(?:ません|ない|なかった|ていません)|"
    r"掲載(?:が|は)?(?:ない|ありません|見当たら|見当たり)|明記(?:は|されて)?(?:い)?(?:ない|ません)|未確認)", I)

EN_SUPER_STRONG = re.compile(
    r"(\bNo\.\s?1\b|\bnumber one\b|#1\b|\bthe only\b|\bonly one\b|\blargest\b|\bbiggest\b|\bsmallest\b|"
    r"\bcheapest\b|\blowest price|\bmost (?:popular|visited|famous|affordable)\b|\bfirst ever\b|"
    r"\bworld'?s (?:first|largest|best|biggest)\b|\btop[- ]rated\b|\branked\b|\b(?:1st|2nd|3rd|\d+th) place\b|"
    r"\bbest-selling\b|\bunique in\b)", I)
EN_SUPER = re.compile(r"\b(best|top \d+|top-\d+|leading|award-winning|unbeatable|unrivaled|unrivalled)\b", I)
JA_SUPER_STRONG = re.compile(
    r"(No\.?\s?1|ナンバーワン|ナンバー1|一番|いちばん|最安|最大|最小|最多|最古|唯一|日本初|世界初|国内初|業界初|"
    r"第?\d+位|ランキング1位|人気1位|売上1位|随一|屈指)")
JA_SUPER = re.compile(r"(最高|最新|トップクラス|ランキング|圧倒的|人気No|定番中の定番)")

EN_STAT = re.compile(
    r"(\baccording to\b|\bsurveys?\b|\bstud(?:y|ies)\b|\bresearch\b|\breports? (?:by|that|from)\b|"
    r"\bdata (?:from|shows?)\b|\bstatistics?\b|\d+(?:\.\d+)?\s?%|\bpercent\b|\bper cent\b|\b\d+ (?:in|out of) \d+\b|"
    r"\bon average\b|\bmajority of\b|\bmost (?:people|families|parents|visitors|reviewers)\b|"
    r"\breviewers? (?:say|said)\b|\bexperts? (?:say|recommend)\b)", I)
JA_STAT = re.compile(
    r"(によると|によれば|調査|アンケート|統計|データ|割合|平均|\d+(?:\.\d+)?\s?%|\d+割(?!引)|人に\d+人|過半数|"
    r"多くの(?:人|家庭|親|方|ママ|パパ)|という声|口コミ|評判|専門家)")
STAT_SOURCED = re.compile(
    r"(according to (?:the )?[A-Z][\w&.-]+|\(\s*source|source:|https?://|\b(?:19|20)\d{2}\b[^.]{0,40}\b(?:survey|study|report)|"
    r"出典[：:]|調べ[）)]|白書|省|庁|総務省|厚生労働省|国土交通省|観光庁|統計局|(?:19|20)\d{2}年[^。]{0,20}(?:調査|統計))", I)

EN_EXP = re.compile(
    r"(\b(?:I|we)\s+(?:visited|went|tried|tested|stayed|ate|used|bought|ordered|took|booked|spent|loved|"
    r"found|noticed|saw|brought|rented|walked|waited|paid|enjoyed|liked|asked)\b|"
    r"\b(?:I|we)'ve (?:been|visited|tried|used|stayed|eaten|tested)\b|"
    r"\bmy (?:kids?|son|daughter|husband|wife|family|partner|toddler|baby|children)\b|"
    r"\bour (?:family|kids|children|visit|trip|stay|experience|toddler|son|daughter)\b|"
    r"\bwhen (?:I|we) (?:visited|went|were)\b|\bin my experience\b|\bfirst-hand\b|\bfirsthand\b|"
    r"\bhands-on\b|\bpersonally\b|\bour team (?:visited|tested|tried)\b)", I)
EN_EXP_GENERIC = re.compile(r"\b(if you (?:visit|go)|your (?:family|kids)|when you (?:visit|go))\b", I)
EN_EXP_DISCLOSED = re.compile(
    r"\b(?:we|I) (?:have not|haven't|did not|didn't|could not|couldn't) (?:yet )?(?:visit|tried|try|test|go|been)\b", I)
JA_EXP = re.compile(
    r"(実際に(?:行|訪|使|食|試|利用|乗|泊|体験|遊|買|購入)|行ってみ|行ってき|訪れてみ|使ってみ|食べてみ|"
    r"試してみ|泊まってみ|遊んでみ|乗ってみ|買ってみ|我が家|わが家|うちの子|うちの(?:娘|息子|夫|妻|家族)|"
    r"(?<![たち])私(?:は|が|も|たち)|筆者(?:は|が|も|の)|編集部(?:が|で|は|も)[^。]{0,15}(?:訪|行|試|取材|調査|体験)|"
    r"実体験|体験談|体験レポ|体験してき|体験しました|取材しました|取材した|"
    r"子ども(?:と|を連れて)[^。]{0,6}(?:行|訪)(?:った|れた|きました|ってきました))")
JA_EXP_GENERIC = re.compile(r"(我が家|わが家)(?:に(?:合う|合った|合わせ|ぴったり)|流|なり)")
JA_EXP_DISCLOSED = re.compile(
    r"((?:実際には?|まだ)[^。]{0,10}(?:行って|訪れて|使って|試して|利用して|体験して)(?:い)?ません|行ったことはありません|"
    r"体験談(?:は|を)(?:載せ|書い)(?:てい)?ません)")

EN_TIME_SENS = re.compile(
    r"\b(limited[- ]time|for a limited time|(?:until|through|thru|ends?|ending|expires?|runs through)\s+"
    r"(?:the end of |end of )?(?:[A-Z][a-z]+\.? \d|\d|[A-Z][a-z]+ (?:19|20)\d{2})|seasonal|"
    r"this (?:year|season|month|summer|winter|spring|fall|autumn|weekend)|currently|right now|"
    r"now (?:offering|available|open)|new(?:ly)? (?:opened|launched|added|renovated)|coming soon|"
    r"starting (?:on |in |from )?(?:[A-Z][a-z]+|\d)|campaign|promotion|on sale|special offer|as of)\b", I)
JA_TIME_SENS = re.compile(
    r"(期間限定|数量限定|季節限定|今だけ|現在|今年|今季|今月|今週|今夏|今冬|この(?:夏|冬|春|秋)|"
    r"新(?:しく|登場|オープン|発売)|オープン予定|予定(?:です|しています)|キャンペーン|セール|開催中|実施中|"
    r"(?:\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|月末|年内|今月|今週|\d{1,2}月)\s?まで|まで(?:の期間|開催|実施|限定|販売)|"
    r"令和\d+年|(?:19|20)\d{2}年)")
YEAR_RE = re.compile(r"(?<![\d$¥€£,])(?:19|20)\d{2}(?![\d,])")

EN_FEATURE = re.compile(
    r"\b(nursing (?:room|area)|baby (?:room|care room)|diaper[- ]changing|changing (?:table|station)s?|"
    r"strollers?|prams?|parking|car park|elevators?|lifts?|wheelchairs?|ramps?|restrooms?|toilets?|"
    r"kids'? menu|children'?s menu|high chairs?|private rooms?|wi-?fi|lockers?|playground|play area|"
    r"gift shop|cafe|café|restaurant|food court|picnic area|shuttle|ticket office|vending machines?|"
    r"smoking area|pets?|dogs?|outlets?|charging|splash pad|pool|petting zoo|feeding|souvenir shop)\b", I)
EN_ATTR_VERB = re.compile(r"\b(has|have|offers?|features?|provides?|includes?|is equipped|comes with|there (?:is|are))\b", I)
JA_FEATURE = re.compile(
    r"(授乳室|ベビールーム|赤ちゃん休憩室|おむつ(?:替え|交換)|オムツ(?:替え|交換)|ベビーカー|駐車場|駐輪場|"
    r"エレベーター|エスカレーター|スロープ|車いす|車椅子|多目的トイレ|トイレ|キッズメニュー|お子様メニュー|"
    r"子ども用(?:いす|椅子|食器)|ベビーチェア|個室|座敷|Wi-?Fi|コインロッカー|ロッカー|遊具|キッズスペース|"
    r"プレイルーム|売店|ショップ|カフェ|レストラン|休憩所|ピクニック|シャトル|送迎|自販機|喫煙|ペット|充電|"
    r"コンセント|プール|じゃぶじゃぶ池|水遊び|ふれあい|えさやり|餌やり|年間パスポート|年パス)")
JA_ATTR_VERB = re.compile(r"(あり|ある|あります|ありません|ない|設置|完備|併設|用意|備え|対応|がある|がない|できる|できます)")

AUDIT_MARKER = re.compile(
    r"(last (?:checked|verified|updated|reviewed)|checked on|verified on|fact-checked|as of\s+\w+|"
    r"確認日|最終確認|最終更新|更新日|時点|現在の情報|確認済み)", I)

FICTION_HEADING = re.compile(r"(example|hypothetical|fictional|sample scenario|illustrative|仮想|想定例|架空|サンプル例|例え話)", I)
METHOD_HEADING = re.compile(
    r"(sources?|references?|how we (?:checked|tested|researched)|methodology|corrections?|what we removed|"
    r"出典|参考(?:文献|資料|リンク)?|確認方法|訂正|外したもの|削除したもの)", I)


def _hits(rx, s):
    return [m.group(0) for m in rx.finditer(s)]


def classify(sentence, lang="auto", heading=False, in_experience_section=False):
    """Return (types: list[str], risk: str, reasons: list[str], flags: dict) for one sentence."""
    s = claimlib.norm(sentence)
    use_en = lang in ("auto", "en")
    use_ja = lang in ("auto", "ja")
    values = claimlib.extract_values(s)
    kinds = {v["kind"] for v in values}
    found = {}   # type -> (risk, reason)
    flags = {}

    def put(t, risk, reason):
        if t not in found or RISK_ORDER[risk] > RISK_ORDER[found[t][0]]:
            found[t] = (risk, reason)

    # first-person experience
    exp = (_hits(EN_EXP, s) if use_en else []) + (_hits(JA_EXP, s) if use_ja else [])
    if exp:
        generic = (use_en and EN_EXP_GENERIC.search(s) and not re.search(r"\b(I|we)\b", s)) or \
                  (use_ja and JA_EXP_GENERIC.search(s) and not re.search(r"(行って|訪れ|使って|食べ|試し)", s))
        disclosed = (use_en and EN_EXP_DISCLOSED.search(s)) or (use_ja and JA_EXP_DISCLOSED.search(s))
        if disclosed:
            flags["experience_disclosed"] = True
        elif not generic:
            put("experience", "high",
                "first-person experience (%s): needs the writer's own record or a neutral rewrite" % exp[0])

    # absence / negation
    absn = (_hits(EN_ABSENCE, s) if use_en else []) + (_hits(JA_ABSENCE, s) if use_ja else [])
    scoped = SCOPED_ABSENCE.search(s)
    if scoped and not absn:
        absn = [scoped.group(0)]
    if absn and not flags.get("experience_disclosed"):
        if scoped:
            put("absence", "low", "scoped absence ('%s'): acceptable form if the places checked are named" % absn[0])
            flags["absence_scoped"] = True
        else:
            put("absence", "high",
                "absence claim ('%s'): 'not found' is not 'does not exist'; check all places first" % absn[0])

    # availability / state
    strong = (_hits(EN_STATE_STRONG, s) if use_en else []) + (_hits(JA_STATE_STRONG, s) if use_ja else [])
    weak = (_hits(EN_STATE, s) if use_en else []) + (_hits(JA_STATE, s) if use_ja else [])
    if strong:
        put("availability", "high", "state word ('%s') changes over time; must be seen on the live rendered page" % strong[0])
    elif weak:
        put("availability", "medium", "availability/permission ('%s'): confirm with the operator's current rules" % weak[0])

    # superlative / ranking
    sup_s = (_hits(EN_SUPER_STRONG, s) if use_en else []) + (_hits(JA_SUPER_STRONG, s) if use_ja else [])
    sup_w = (_hits(EN_SUPER, s) if use_en else []) + (_hits(JA_SUPER, s) if use_ja else [])
    if sup_s:
        put("superlative", "high", "superlative/ranking ('%s') needs a named, dated source" % sup_s[0])
    elif sup_w:
        put("superlative", "medium", "evaluative superlative ('%s'): opinion unless sourced" % sup_w[0])

    # statistic / attribution
    stat = (_hits(EN_STAT, s) if use_en else []) + (_hits(JA_STAT, s) if use_ja else [])
    if stat or "percent" in kinds:
        cue = stat[0] if stat else "%"
        if STAT_SOURCED.search(s):
            put("statistic", "medium", "statistic/attribution ('%s') names a source: open the original" % cue)
        else:
            put("statistic", "high", "statistic/attribution ('%s') without a named, dated source" % cue)

    # price
    if "price" in kinds:
        raw = [v["raw"] for v in values if v["kind"] == "price"][0]
        put("price", "medium", "price (%s): prices change; record date and tax/age conditions" % raw)

    # time / dates
    hours_words = (use_en and re.search(r"\b(opening hours|hours|opens?|closes?|closed on|last (?:entry|admission|order)|"
                                        r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)days?|holidays?)\b", s, I)) or \
                  (use_ja and re.search(r"(営業時間|開館時間|開園時間|定休日|休館日|休園日|最終入(?:場|館|園)|ラストオーダー|"
                                        r"[月火水木金土日]曜|祝日|午前|午後)", s))
    strong_hours = (use_en and re.search(r"\b(opening hours|closed on|closed every|last (?:entry|admission|order)|"
                                         r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)days?|public holidays?)\b", s, I)) or \
                   (use_ja and re.search(r"(営業時間|開館時間|開園時間|定休日|休館日|休園日|最終入(?:場|館|園)|ラストオーダー|"
                                         r"[月火水木金土日]曜|祝日)", s))
    if "time" in kinds or ("date" in kinds and any(not v.get("year_only") for v in values if v["kind"] == "date")) or hours_words:
        raws = [v["raw"] for v in values if v["kind"] in ("time", "date") and not v.get("year_only")]
        cue = raws[0] if raws else (hours_words.group(0) if hasattr(hours_words, "group") else "hours")
        put("time", "medium" if (raws or strong_hours) else "low",
            "time/hours/date (%s): confirm on the operator's calendar incl. exceptions" % cue)

    # quantity
    if "quantity" in kinds:
        raw = [v["raw"] for v in values if v["kind"] == "quantity"][0]
        put("quantity", "low", "quantity (%s)" % raw)

    # time-sensitive
    ts = (_hits(EN_TIME_SENS, s) if use_en else []) + (_hits(JA_TIME_SENS, s) if use_ja else [])
    if ts or YEAR_RE.search(s):
        cue = ts[0] if ts else YEAR_RE.search(s).group(0)
        put("time_sensitive", "medium", "time-sensitive ('%s'): add an end date / re-check date" % cue)

    # named entity + attribute
    ents, _ = claimlib.key_terms(s)
    feat = (_hits(EN_FEATURE, s) if use_en else []) + (_hits(JA_FEATURE, s) if use_ja else [])
    verb = (use_en and EN_ATTR_VERB.search(s)) or (use_ja and JA_ATTR_VERB.search(s))
    if ents and (feat or verb):
        put("entity_attribute", "medium",
            "named entity + attribute (%s / %s): confirm on the entity's own page" % (ents[0], feat[0] if feat else verb.group(0)))
    elif feat and verb:
        put("entity_attribute", "medium", "facility feature ('%s'): confirm on the facility's own page" % feat[0])

    # quantity next to an entity is more than low
    if "quantity" in found and ents:
        put("quantity", "medium", found["quantity"][1] + " about a named entity")

    if in_experience_section and not heading and "experience" not in found and not flags.get("experience_disclosed"):
        put("experience", "high",
            "sentence inside a first-person experience section: needs the writer's own record or removal")
    if heading and found:
        # A heading is a label, not a statement: keep only what a heading can assert.
        keep = {}
        for t, (r, why) in found.items():
            if t == "experience":
                keep[t] = ("medium", "experience section heading ('%s'): every sentence under it needs a record" % exp[0])
            elif t in ("price", "quantity") or (t == "time" and any(v["kind"] == "time" or (v["kind"] == "date" and not v.get("year_only")) for v in values)):
                keep[t] = (r, why)
            elif t == "superlative" or (t == "availability" and r == "high"):
                keep[t] = (r, why)
        found = keep
    if not found:
        return [], None, [], flags
    order = sorted(found, key=lambda t: (-RISK_ORDER[found[t][0]], TIE_ORDER.index(t)))
    risk = found[order[0]][0]
    reasons = [found[t][1] for t in order]
    return order, risk, reasons, flags


def feature_terms(sentence):
    s = claimlib.norm(sentence)
    out = []
    for m in list(EN_FEATURE.finditer(s)) + list(JA_FEATURE.finditer(s)):
        t = m.group(0).casefold()
        if t.isascii() and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        if t not in out:
            out.append(t)
    return out


def build(path, lang="auto", fmt="auto", known=None):
    blocks, hidden, fmt = claimlib.load_document(path, fmt)
    visible_text = " ".join(b["text"] for b in blocks)
    detected = claimlib.detect_lang(visible_text)
    known = known or []

    claims = []
    markers = []
    skipped = {"disclosed_fiction_section": 0, "sources_or_method_section": 0, "known": 0}
    section_stack = []  # (level, kind)
    n = 0
    sentences_scanned = 0
    for b in blocks:
        if b["heading"]:
            lvl = b["heading"]
            while section_stack and section_stack[-1][0] >= lvl:
                section_stack.pop()
            if FICTION_HEADING.search(b["text"]):
                kind = "fiction"
            elif METHOD_HEADING.search(b["text"]):
                kind = "method"
            elif "experience" in classify(b["text"], lang, heading=True)[0]:
                kind = "experience"
            else:
                kind = ""
            section_stack.append((lvl, kind))
        skip_kind = next((k for _, k in reversed(section_stack) if k), "")
        in_exp = skip_kind == "experience"
        for sent in claimlib.split_sentences(b["text"], lang):
            sentences_scanned += 1
            if AUDIT_MARKER.search(claimlib.norm(sent)):
                markers.append({"line": b["line"], "text": sent})
            types, risk, reasons, flags = classify(sent, lang, heading=bool(b["heading"]), in_experience_section=in_exp)
            if not types:
                continue
            if skip_kind == "fiction" and not b["heading"]:
                skipped["disclosed_fiction_section"] += 1
                continue
            if skip_kind == "method" and not b["heading"]:
                skipped["sources_or_method_section"] += 1
                continue
            n += 1
            ents, attrs = claimlib.key_terms(sent)
            is_known = any(k and k in claimlib.fold(sent) for k in known)
            claim = {
                "id": "C%03d" % n,
                "line": b["line"],
                "in_heading": bool(b["heading"]),
                "text": sent,
                "types": types,
                "primary_type": types[0],
                "risk": risk,
                "reasons": reasons,
                "how_to_verify": [HINT[t] for t in types],
                "values": [{k: v for k, v in val.items()} for val in claimlib.extract_values(sent)],
                "entity_terms": ents,
                "attr_terms": attrs,
                "feature_terms": feature_terms(sent),
                "status": "unverified",
                "known": is_known,
            }
            if flags:
                claim["flags"] = flags
            if is_known:
                skipped["known"] += 1
            claims.append(claim)

    hidden_out = []
    for i, h in enumerate(hidden, start=1):
        types, risk, reasons, _ = classify(h["text"], lang)
        item = {
            "id": "H%02d" % i,
            "kind": h["kind"],
            "line": h["line"],
            "text": h["text"][:500],
            "note": "hidden text, not visible to readers: do not audit it as published content and "
                    "do not use it as evidence; check whether it is stale and should be removed",
            "claim_types_inside": types,
        }
        if h.get("tag"):
            item["tag"] = h["tag"]
        hidden_out.append(item)

    counts = {"total": len(claims), "by_risk": {"high": 0, "medium": 0, "low": 0}, "by_type": {}}
    for c in claims:
        counts["by_risk"][c["risk"]] += 1
        for t in c["types"]:
            counts["by_type"][t] = counts["by_type"].get(t, 0) + 1
    return {
        "tool": "content-fact-auditor/extract_claims.py",
        "version": VERSION,
        "source_file": os.path.basename(path),
        "format": fmt,
        "lang_option": lang,
        "lang_detected": detected,
        "sentences_scanned": sentences_scanned,
        "counts": counts,
        "skipped": skipped,
        "audit_date_markers": markers,
        "audit_date_marker_note": (
            "A 'checked on' / 確認日 date in one place does not mean every claim was checked. "
            "Treat each claim separately." if markers else ""),
        "hidden_text": hidden_out,
        "claims": claims,
    }


def filter_min_risk(result, min_risk):
    floor = RISK_ORDER[min_risk]
    result = dict(result)
    result["claims"] = [c for c in result["claims"] if RISK_ORDER[c["risk"]] >= floor]
    result["min_risk"] = min_risk
    return result


CSV_FIELDS = ["id", "line", "risk", "primary_type", "types", "text", "reasons", "values", "status", "known"]


def write_csv(result, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for c in result["claims"]:
            w.writerow([
                c["id"], c["line"], c["risk"], c["primary_type"], ";".join(c["types"]), c["text"],
                " | ".join(c["reasons"]),
                "; ".join("%s=%s%s" % (v["kind"], v["value"], (" " + v["unit"]) if v.get("unit") else "") for v in c["values"]),
                c["status"], "yes" if c["known"] else "",
            ])


def _md_escape(s):
    return s.replace("|", "\\|").replace("\n", " ")


def write_checklist(result, path):
    L = []
    L.append("# Claim checklist: %s" % result["source_file"])
    L.append("")
    L.append("Generated by extract_claims.py %s. Every item starts as **unverified**. "
             "This list does not say anything is true or false." % result["version"])
    L.append("")
    cr = result["counts"]["by_risk"]
    L.append("- Claims: %d (high %d / medium %d / low %d)%s" % (
        len(result["claims"]), sum(1 for c in result["claims"] if c["risk"] == "high"),
        sum(1 for c in result["claims"] if c["risk"] == "medium"),
        sum(1 for c in result["claims"] if c["risk"] == "low"),
        (" — filtered to risk >= %s" % result["min_risk"]) if result.get("min_risk", "low") != "low" else ""))
    L.append("- Hidden text blocks (not visible to readers): %d" % len(result["hidden_text"]))
    L.append("- Language detected: %s" % result["lang_detected"])
    if result["audit_date_markers"]:
        L.append("- Audit-date markers found: %d. %s" % (len(result["audit_date_markers"]), result["audit_date_marker_note"]))
    sk = result["skipped"]
    if sk["disclosed_fiction_section"] or sk["sources_or_method_section"]:
        L.append("- Skipped sentences: %d in sections labeled example/hypothetical, %d in sources/method/corrections sections" % (
            sk["disclosed_fiction_section"], sk["sources_or_method_section"]))
    L.append("")
    exp = [c for c in result["claims"] if "experience" in c["types"]]
    if exp:
        L.append("## First-person experience (needs the writer's own record)")
        L.append("")
        for c in exp:
            L.append("- [ ] **%s** (line %d) %s" % (c["id"], c["line"], c["text"]))
        L.append("")
    for risk in ("high", "medium", "low"):
        items = [c for c in result["claims"] if c["risk"] == risk and not c["known"]]
        if not items:
            continue
        L.append("## %s risk (%d)" % (risk.capitalize(), len(items)))
        L.append("")
        for c in items:
            L.append("- [ ] **%s** (line %d, %s) %s" % (c["id"], c["line"], ", ".join(c["types"]), c["text"]))
            L.append("  - why: %s" % c["reasons"][0])
            L.append("  - check: %s" % c["how_to_verify"][0])
        L.append("")
    known = [c for c in result["claims"] if c["known"]]
    if known:
        L.append("## Already in the --known list (%d)" % len(known))
        L.append("")
        for c in known:
            L.append("- %s (line %d) %s" % (c["id"], c["line"], c["text"]))
        L.append("")
    L.append("## Hidden text, not visible to readers")
    L.append("")
    if result["hidden_text"]:
        L.append("Do not audit these as published claims and do not use them as evidence. "
                 "They often hold stale prices or old notices; decide whether to delete them.")
        L.append("")
        L.append("| id | kind | line | text | claim types inside |")
        L.append("|---|---|---|---|---|")
        for h in result["hidden_text"]:
            L.append("| %s | %s | %d | %s | %s |" % (h["id"], h["kind"], h["line"], _md_escape(h["text"][:160]),
                                                    ", ".join(h["claim_types_inside"]) or "-"))
    else:
        L.append("None found.")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def load_known(path):
    if not path:
        return []
    if not os.path.isfile(path):
        raise ValueError("--known file not found: %s" % path)
    out = []
    for line in claimlib.read_text_file(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(claimlib.fold(line))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract checkable claims from an article (offline).")
    ap.add_argument("article", help="article file (.md, .html, .txt)")
    ap.add_argument("--out-dir", default="claims-out", help="output folder (created if missing)")
    ap.add_argument("--lang", default="auto", choices=["auto", "ja", "en"])
    ap.add_argument("--min-risk", default="low", choices=["low", "medium", "high"])
    ap.add_argument("--format", default="auto", choices=["auto", "md", "html", "txt"])
    ap.add_argument("--known", help="text file: one substring per line of claims already verified (listed separately)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.article):
        print("error: article file not found: %s" % args.article, file=sys.stderr)
        return 2
    try:
        known = load_known(args.known)
        result = build(args.article, lang=args.lang, fmt=args.format, known=known)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    result = filter_min_risk(result, args.min_risk)
    os.makedirs(args.out_dir, exist_ok=True)
    jp = os.path.join(args.out_dir, "claims.json")
    cp = os.path.join(args.out_dir, "claims.csv")
    mp = os.path.join(args.out_dir, "claims-checklist.md")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    write_csv(result, cp)
    write_checklist(result, mp)
    r = {k: sum(1 for c in result["claims"] if c["risk"] == k) for k in ("high", "medium", "low")}
    print("Extracted %d claims (high %d, medium %d, low %d) and %d hidden-text blocks from %s" % (
        len(result["claims"]), r["high"], r["medium"], r["low"], len(result["hidden_text"]), args.article))
    print("Wrote %s, %s, %s" % (jp, cp, mp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
