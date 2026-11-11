#!/usr/bin/env python3
"""质量检查：2026-11-11 静态早报的 content-v2 字段。

不作为发布门禁，也不检查定时排期。严格覆盖率里，原文 403 的三条重点正文允许为空。
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "spec" / "sample-v2" / "check_v2.py"
DIGEST = ROOT / "data" / "digest" / "2026-11-11.json"
LATEST = ROOT / "data" / "digest" / "latest.json"
# 原文页面返回 403。main 上的新摘要仍不够写成 300 字正文，故留空。
OPENAI_403 = {
    "n46ecb159c153",
    "n5ca4dc7b6d88",
    "n3588ceed4155",
}
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


class ContentV2FieldsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.digest = load(DIGEST)
        cls.latest = load(LATEST)

    def test_checker_passes_without_being_a_publish_gate(self):
        proc = subprocess.run(
            [sys.executable, str(CHECK), str(DIGEST), "--img-root", str(ROOT / "data")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("通过", proc.stdout)
        self.assertNotIn("不通过", proc.stdout)

    def test_latest_matches_dated_digest_and_keeps_main_timestamp(self):
        self.assertEqual(self.latest, self.digest)
        self.assertEqual(self.digest["date"], "2026-11-11")
        self.assertEqual(self.digest["generated_at"], "2026-11-11T09:46:23+08:00")
        self.assertEqual(self.digest["summary_mode"], "ai")
        self.assertEqual(len(self.digest["items"]), 50)
        self.assertTrue(OPENAI_403.isdisjoint(self.digest["top_items"]))
        digests = load(ROOT / "data" / "digests.json")
        self.assertEqual(digests["digests"][0]["generated_at"], self.digest["generated_at"])

    def test_titles_leads_and_key_bodies(self):
        items = self.digest["items"]
        self.assertEqual(sum(1 for n in items if n["title_zh"]), 50)
        self.assertEqual(sum(1 for n in items if n["lead_zh"]), 50)
        must = [
            n
            for n in items
            if n["id"] in self.digest["top_items"] or n.get("importance", 1) >= 2
        ]
        self.assertEqual(len(must), 22)
        empty = {n["id"] for n in must if not n["body_zh"]}
        self.assertEqual(empty, OPENAI_403)
        for n in items:
            if n["id"] not in OPENAI_403 and (
                n["id"] in self.digest["top_items"] or n.get("importance", 1) >= 2
            ):
                self.assertTrue(n["body_zh"], n["id"])
        main = json.loads(
            subprocess.check_output(
                ["git", "show", "origin/main:data/digest/2026-11-11.json"],
                cwd=ROOT,
            )
        )
        self.assertEqual(self.digest["top_items"], main["top_items"])
        self.assertEqual(
            [n["id"] for n in self.digest["items"]],
            [n["id"] for n in main["items"]],
        )
        for published, current in zip(main["items"], self.digest["items"]):
            for key in OLD:
                self.assertEqual(published[key], current[key], (current["id"], key))

    def test_new_fields_are_empty_string_or_list_and_old_fields_remain(self):
        for n in self.digest["items"]:
            for key in OLD:
                self.assertIn(key, n)
            for key in NEW:
                self.assertIn(key, n)
                self.assertIsNotNone(n[key])
            self.assertIsInstance(n["title_zh"], str)
            self.assertIsInstance(n["lead_zh"], str)
            self.assertIsInstance(n["body_zh"], list)
            for key in ("image_url", "image_source", "image_origin_url"):
                self.assertIsInstance(n[key], str)
            if n["image_url"]:
                self.assertTrue(n["image_source"])
                self.assertTrue(n["image_origin_url"].startswith("https://"))
            else:
                self.assertEqual(n["image_source"], "")
                self.assertEqual(n["image_origin_url"], "")
            news = load(ROOT / "data" / "news" / f"{n['id']}.json")
            self.assertEqual(news, n)

    def test_thumbnails_match_source_hash_and_size(self):
        seen = 0
        for n in self.digest["items"]:
            if not n["image_url"]:
                continue
            seen += 1
            digest = hashlib.sha1(n["image_origin_url"].encode("utf-8")).hexdigest()
            self.assertEqual(n["image_url"], f"img/{digest}.jpg")
            path = ROOT / "data" / n["image_url"]
            self.assertTrue(path.is_file(), path)
            self.assertLessEqual(path.stat().st_size, 100 * 1024)
            self.assertIn(n["image_source"], {s["name"] for s in n["sources"]})
        self.assertGreater(seen, 0)

    def test_h5_page_was_not_switched_to_v2(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("title_zh", html)
        self.assertNotIn("body_zh", html)


if __name__ == "__main__":
    unittest.main()
