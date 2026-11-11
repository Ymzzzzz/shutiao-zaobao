#!/usr/bin/env python3
"""检查最新一期早报的 content-v2 字段是否结构合法。

日期从 data/digest/latest.json 读取，缺失时再看 data/digests.json。
不写死某一天或 generated_at。空标题、空导语、空正文和没有配图都算合法，
覆盖率不作为失败条件。
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "digest" / "latest.json"
DIGESTS = ROOT / "data" / "digests.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NEW = [
    "title_zh",
    "lead_zh",
    "body_zh",
    "image_url",
    "image_source",
    "image_origin_url",
]
OLD = [
    "analysis",
    "category",
    "claims",
    "facts",
    "id",
    "importance",
    "original_title",
    "published_at",
    "sources",
    "status",
    "summary",
    "summary_mode",
    "title",
    "updated_at",
    "verified",
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def index_dates():
    if not DIGESTS.is_file():
        return []
    raw = load(DIGESTS)
    entries = raw.get("digests") if isinstance(raw, dict) else raw
    dates = []
    for entry in entries or []:
        if isinstance(entry, dict) and DATE_RE.match(str(entry.get("date") or "")):
            dates.append(entry["date"])
    return dates


def latest_date(latest):
    date = str(latest.get("date") or "")
    if DATE_RE.match(date):
        return date
    dates = index_dates()
    if not dates:
        raise AssertionError("latest.json 没有日期，digests.json 也没有可用日期")
    return max(dates)


class ContentV2FieldsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.latest = load(LATEST)
        cls.date = latest_date(cls.latest)
        cls.dated_path = ROOT / "data" / "digest" / f"{cls.date}.json"
        cls.digest = load(cls.dated_path)

    def test_latest_matches_dated_file(self):
        self.assertTrue(self.dated_path.is_file(), self.dated_path)
        self.assertEqual(self.latest, self.digest)
        self.assertEqual(self.digest.get("date"), self.date)
        dates = index_dates()
        if dates:
            self.assertEqual(max(dates), self.date)
            self.assertIn(self.date, dates)

    def test_new_fields_are_empty_string_or_list_and_old_fields_remain(self):
        items = self.digest.get("items") or []
        self.assertIsInstance(items, list)
        ids = set()
        for n in items:
            self.assertIsInstance(n, dict)
            self.assertTrue(n.get("id"))
            self.assertNotIn(n["id"], ids)
            ids.add(n["id"])
            for key in OLD:
                self.assertIn(key, n, n["id"])
            for key in NEW:
                self.assertIn(key, n, n["id"])
                self.assertIsNotNone(n[key], (n["id"], key))
            self.assertIsInstance(n["title_zh"], str, n["id"])
            self.assertIsInstance(n["lead_zh"], str, n["id"])
            self.assertIsInstance(n["body_zh"], list, n["id"])
            for key in ("image_url", "image_source", "image_origin_url"):
                self.assertIsInstance(n[key], str, (n["id"], key))
            if n["image_url"]:
                self.assertTrue(n["image_source"], n["id"])
                self.assertTrue(n["image_origin_url"].startswith("https://"), n["id"])
            else:
                self.assertEqual(n["image_source"], "", n["id"])
                self.assertEqual(n["image_origin_url"], "", n["id"])
            news = load(ROOT / "data" / "news" / f"{n['id']}.json")
            self.assertEqual(news, n, n["id"])
        for top_id in self.digest.get("top_items") or []:
            self.assertIn(top_id, ids, top_id)

    def test_thumbnails_match_source_hash_and_size(self):
        for n in self.digest.get("items") or []:
            if not n.get("image_url"):
                continue
            digest = hashlib.sha1(n["image_origin_url"].encode("utf-8")).hexdigest()
            self.assertEqual(n["image_url"], f"img/{digest}.jpg", n["id"])
            path = ROOT / "data" / n["image_url"]
            self.assertTrue(path.is_file(), path)
            self.assertLessEqual(path.stat().st_size, 100 * 1024, n["id"])
            names = {s.get("name") for s in n.get("sources") or [] if isinstance(s, dict)}
            self.assertIn(n["image_source"], names, n["id"])

    def test_h5_page_was_not_switched_to_v2(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("title_zh", html)
        self.assertNotIn("body_zh", html)


if __name__ == "__main__":
    unittest.main()
