"""Synthetic Meta Ads answers for the evals, in the shape of the real `ads_get_ad_entities` answers.

The example runs' answers (handoff/refresh-ad_v02/examples/*/01_base) carry real ad ids, names and
account figures, so none of it is copied here. What is kept is the *shape* of a row: every number a
string, money as {"value", "unit"}, rates with a percent sign, results as {"values": [{"value"}]}.
The numbers are generated: the ad fades the way the scenario says; ids and names are made up.

Used by gen_mocks.py (writes the committed fixtures) and by the fixture scripts.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

TODAY = date(2026, 11, 5)          # the eval's fixed "today"; R1 cuts the last two days
LAST = TODAY - timedelta(days=2)   # 2026-11-03
DAYS = 91                          # 13 whole weeks ending on LAST
ACCOUNT_ID = "9990000001"
AD_A, AD_B = "100000000000001", "100000000000002"
NAME_A, NAME_B = "Example ebook", "Example ebook B"
# More ads that run the same video file as AD_A (the structural check, R2b): older ads of the account,
# so they are not in the 13-week ranking. VIDEO_A is AD_A's file, VIDEO_B AD_B's (another file).
AD_C, AD_D, AD_E = "100000000000003", "100000000000004", "100000000000005"
VIDEO_A, VIDEO_B = "200000000000001", "200000000000002"
SYNTHETIC_IDS = {ACCOUNT_ID, AD_A, AD_B, AD_C, AD_D, AD_E, VIDEO_A, VIDEO_B}
# hook, middle, account_drop: v1's rows (no retention ladder). middle_ladder: the hook holds and the
# conditional step p75/p50 drops 6 points (HANDOFF 9b RC4). ad3: the hook fades and the ladder's
# steps stay as they are, in Ad 3's shape (RC1: the middle is not fading).
SCENARIOS = ("hook", "middle", "account_drop", "middle_ladder", "ad3")

# Ad 3's conditional steps (handoff v03 ad3-middle-recut middle_diagnosis.md section 1, peak window):
# p50/p25, p75/p50, p95/p75, p100/p95.
AD3_STEPS = (0.580, 0.556, 0.617, 0.897)


def _ladder(v: dict, p25_per_play: float, steps: tuple[float, ...], avg_s: int) -> dict:
    """The retention ladder for a day's figures: plays from p25, then each step of `steps`."""
    p50 = round(v["p25"] * steps[0])
    p75 = round(p50 * steps[1])
    p95 = round(p75 * steps[2])
    return dict(plays=round(v["p25"] / p25_per_play), p50=p50, p75=p75, p95=p95,
                p100=round(p95 * steps[3]), avg=avg_s)


def _day_values(scn: str, ad: str, i: int) -> dict:
    """One day's figures for the ad, day index i = 0 (oldest) .. 90 (LAST)."""
    fading = i >= DAYS - 28
    wob = (i % 3) - 1  # -1, 0, 1: small wobble so the series does not look machine-made
    if ad == AD_A:
        v = dict(spend=300.0 + 4 * wob, imp=3000 + 40 * wob, p25=750 + 10 * wob, thru=340 + 5 * wob,
                 ctr=3.5, res=10 + (1 if i % 2 else 0))
        if fading and scn in ("hook", "ad3"):
            v.update(p25=500 + 8 * wob, thru=225 + 4 * wob, ctr=2.3, res=6)
        if fading and scn in ("middle", "middle_ladder"):
            v.update(spend=480.0 + 4 * wob, thru=190 + 4 * wob)
        if fading and scn == "account_drop":
            v.update(p25=450 + 8 * wob, thru=205 + 4 * wob, ctr=2.1, res=6)
        if scn == "middle_ladder":  # p75/p50 0.556 -> 0.496 in the fading weeks, the rest held
            steps = (0.580, 0.496 if fading else 0.556, 0.617, 0.897)
            v.update(_ladder(v, 0.32, steps, 6 if fading else 7))
        if scn == "ad3":  # the hook fades (p25 per impression), the conditional steps hold
            v.update(_ladder(v, 0.32 if not fading else 0.30, AD3_STEPS, 6 if fading else 7))
    else:  # a steady ad; in the account-drop scenario it falls just as far
        v = dict(spend=250.0 + 3 * wob, imp=2600 + 30 * wob, p25=640 + 8 * wob, thru=290 + 4 * wob,
                 ctr=3.1, res=7 + (1 if i % 2 else 0))
        if fading and scn == "account_drop":
            v.update(p25=380 + 6 * wob, thru=175 + 3 * wob, ctr=1.9, res=4)
        if scn in ("middle_ladder", "ad3"):
            v.update(_ladder(v, 0.30, (0.540, 0.600, 0.640, 0.900), 7))
    return v


LADDER_FIELDS = (("plays", "video_play_actions"), ("p50", "video_p50_watched_actions"),
                 ("p75", "video_p75_watched_actions"), ("p95", "video_p95_watched_actions"),
                 ("p100", "video_p100_watched_actions"))


def _row(ad: str, name: str, start: date, stop: date, v: dict, days: int) -> dict:
    spend, imp, res = v["spend"] * days, int(v["imp"] * days), int(v["res"] * days)
    ladder = {}
    if "plays" in v:  # the retention ladder R2 reads (Meta: counts as strings, whole seconds)
        ladder = {field: str(int(v[k] * days)) for k, field in LADDER_FIELDS}
        ladder["video_avg_time_watched_actions"] = str(int(round(v["avg"])))
    return {**_base_row(ad, name, start, stop, v, days, spend, imp, res), **ladder}


def _base_row(ad: str, name: str, start: date, stop: date, v: dict, days: int, spend: float, imp: int,
              res: int) -> dict:
    return {
        "id": ad, "name": name, "date_start": start.isoformat(), "date_stop": stop.isoformat(),
        "amount_spent": {"value": f"{spend:.2f}", "unit": "PLN"},
        "impressions": str(imp),
        "frequency": "1.150000",
        "cpm": {"value": f"{spend / imp * 1000:.2f}", "unit": "PLN"},
        "unique_link_clicks_ctr": f"{v['ctr']:.6f}",
        "video_p25_watched_actions": str(int(v["p25"] * days)),
        "video_thruplay_watched_actions": str(int(v["thru"] * days)),
        "results": {"indicator": "actions:offsite_conversion.fb_pixel_purchase",
                    "values": [{"attribution_windows": ["default"], "value": str(res)}]},
        "cost_per_result": {"value": f"{spend / res:.2f}", "unit": "PLN",
                            "conversion_type": "Website purchases"},
    }


def _sum(rows_v: list[dict]) -> dict:
    n = len(rows_v)
    keys = ("spend", "imp", "p25", "thru", "res")
    if "plays" in rows_v[0]:
        keys += ("plays", "p50", "p75", "p95", "p100", "avg")
    out = {k: sum(r[k] for r in rows_v) / n for k in keys}
    out["ctr"] = sum(r["ctr"] * r["imp"] for r in rows_v) / sum(r["imp"] for r in rows_v)
    return out


def daily(scn: str, ad: str, name: str, last_n: int = DAYS) -> list[dict]:
    first_i = DAYS - last_n
    return [_row(ad, name, d := LAST - timedelta(days=DAYS - 1 - i), d, _day_values(scn, ad, i), 1)
            for i in range(first_i, DAYS)]


def weekly(scn: str, ad: str, name: str) -> list[dict]:
    rows = []
    for w in range(DAYS // 7):
        idx = range(w * 7, w * 7 + 7)
        start = LAST - timedelta(days=DAYS - 1 - idx[0])
        rows.append(_row(ad, name, start, start + timedelta(days=6),
                         _sum([_day_values(scn, ad, i) for i in idx]), 7))
    return rows


def account_weekly(scn: str) -> list[dict]:
    a, b = weekly(scn, AD_A, NAME_A), weekly(scn, AD_B, NAME_B)
    out = []
    for ra, rb in zip(a, b):
        tot = {"spend": 0.0, "imp": 0, "p25": 0, "thru": 0, "res": 0, "ctrw": 0.0}
        for r in (ra, rb):
            tot["spend"] += float(r["amount_spent"]["value"])
            tot["imp"] += int(r["impressions"])
            tot["p25"] += int(r["video_p25_watched_actions"])
            tot["thru"] += int(r["video_thruplay_watched_actions"])
            tot["res"] += int(r["results"]["values"][0]["value"])
            tot["ctrw"] += float(r["unique_link_clicks_ctr"]) * int(r["impressions"])
        v = dict(spend=tot["spend"], imp=tot["imp"], p25=tot["p25"], thru=tot["thru"], res=tot["res"],
                 ctr=tot["ctrw"] / tot["imp"])
        if "video_play_actions" in ra:
            for k, field in LADDER_FIELDS:
                v[k] = int(ra[field]) + int(rb[field])
            v["avg"] = (int(ra["video_avg_time_watched_actions"]) + int(rb["video_avg_time_watched_actions"])) / 2
        out.append(_row(ACCOUNT_ID, "Example account", date.fromisoformat(ra["date_start"]),
                        date.fromisoformat(ra["date_stop"]), v, 1))
    return out


def mcp_answer(rows: list[dict]) -> dict:
    """`ads_get_ad_entities` as the Meta MCP answers it: the rows as a JSON text next to its own id."""
    return {"ad_entities": json.dumps(rows, ensure_ascii=False), "client_conversation_id": "eval-mock-0001"}


def rows_of(answer: dict) -> list[dict]:
    """The rows of an `mcp_answer`."""
    return json.loads(answer["ad_entities"])


def answers(scn: str) -> dict[str, dict]:
    """The mock answers by `<level>_<time_increment>` (the file name the mock tool picks)."""
    ads_w = weekly(scn, AD_A, NAME_A) + weekly(scn, AD_B, NAME_B)
    ads_d = daily(scn, AD_A, NAME_A, 28) + daily(scn, AD_B, NAME_B, 28)
    return {
        "ad_7": mcp_answer(ads_w),
        "account_7": mcp_answer(account_weekly(scn)),
        "ad_1": mcp_answer(ads_d),
    }


# --- the structural check (R2b): the same file in several ads --------------------------------------

# Whole-life totals per upload of Ad 3's file (handoff v03 ad3-middle-recut middle_diagnosis.md
# section 2, the engine test fixture ad3_same_file_uploads.json): plays, p25, p50, p75, p95, p100.
# The ids are synthetic; AD_A is the "[PL] LD Sales" ad, the one the ranking chose.
AD3_UPLOADS = {
    AD_A: ("2026-08-07", (55353, 16560, 9513, 5293, 3315, 2983)),
    AD_C: ("2026-05-22", (5971, 1874, 1109, 545, 340, 312)),
    AD_D: ("2026-05-24", (5219, 1740, 1014, 540, 331, 285)),
    AD_E: ("2026-05-29", (11870, 4802, 3219, 1987, 1379, 1246)),
}
# AD_B runs another file; its weakest step is p50/p25, so counting it would break the shared shape.
OTHER_UPLOAD = {AD_B: ("2026-08-01", (48210, 14463, 7810, 4686, 2999, 2699))}
# RC4's ad: its file runs in this ad only (no other upload: R2b says "not structural").
MIDDLE_UPLOADS = {AD_A: ("2026-08-07", (61420, 19654, 11399, 6338, 3910, 3507))}
LENGTHS = {"ad3": 24.149, "middle_ladder": 30.0, "hook": 30.0, "account_drop": 30.0}   # AD_A's file: 30 s
NAMES = {AD_A: NAME_A, AD_B: NAME_B, AD_C: "Example ebook (traffic)", AD_D: "Example ebook (sales)",
         AD_E: "Example ebook (checkout)"}


def _lifetime_row(ad: str, start: str, counts: tuple[int, ...]) -> dict:
    keys = ("video_play_actions", "video_p25_watched_actions", "video_p50_watched_actions",
            "video_p75_watched_actions", "video_p95_watched_actions", "video_p100_watched_actions")
    return {"id": ad, "name": NAMES[ad], "date_start": start, "date_stop": LAST.isoformat(),
            **{k: str(c) for k, c in zip(keys, counts)}}


def uploads(scn: str) -> dict[str, tuple[str, tuple[int, ...]]]:
    """Every ad of the account with its whole-life ladder counts, for `ads_get_ad_entities`."""
    return {**(AD3_UPLOADS if scn == "ad3" else MIDDLE_UPLOADS), **OTHER_UPLOAD}


def lifetime(scn: str) -> dict:
    """`ads_get_ad_entities` at ad level over each ad's whole life: one total row per ad."""
    return mcp_answer([_lifetime_row(ad, start, counts) for ad, (start, counts) in uploads(scn).items()])


def same_file(scn: str) -> list[str]:
    """The ads that run AD_A's file, AD_A first."""
    return [ad for ad in uploads(scn) if ad != AD_B]


def creatives(scn: str) -> dict:
    """`ads_get_creatives` across the account: each ad's creative with its video id and thumbnail."""
    out = []
    for ad in uploads(scn):
        video = VIDEO_B if ad == AD_B else VIDEO_A
        out.append({"ad_id": ad, "name": NAMES[ad], "primary_text": "Example primary text for the ebook.",
                    "headline": "Example ebook", "call_to_action_type": "LEARN_MORE",
                    "video_id": video, "thumbnail_url": f"https://example.invalid/thumb_{video}.jpg"})
    return {"data": out}


def videos(scn: str) -> dict:
    """`ads_get_ad_videos`: each file's id and length (the download links are null, as Meta gives them)."""
    return {"data": [
        {"id": VIDEO_A, "length": LENGTHS[scn], "title": NAME_A, "preview_url": "https://example.invalid/preview_a.mp4",
         "download_hd_url": None, "download_sd_url": None, "thumbnail_url": f"https://example.invalid/thumb_{VIDEO_A}.jpg"},
        {"id": VIDEO_B, "length": 21.5, "title": NAME_B, "preview_url": "https://example.invalid/preview_b.mp4",
         "download_hd_url": None, "download_sd_url": None, "thumbnail_url": f"https://example.invalid/thumb_{VIDEO_B}.jpg"}]}
