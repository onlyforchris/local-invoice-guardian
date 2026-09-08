# -*- coding: utf-8 -*-
"""发票管家 HTTP 接口冒烟测试。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8799"


def call(path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.read()


# 1) 首页
s, html = call("/")
print("GET /            ->", s, "html bytes:", len(html), "| 含标题:", "发票管家" in html.decode("utf-8", "ignore"))
# 2) config / folders / categories
s, cfg = call("/api/config")
print("GET /api/config  ->", s, json.loads(cfg))
s, folders = call("/api/folders")
print("GET /api/folders ->", s, json.loads(folders)["folders"])
s, cats = call("/api/categories")
print("GET /api/categories ->", s, "科目数:", len(json.loads(cats)))
# 3) 使用当前配置扫描（无目录时也能完成接口检查，不内置作者路径）
body = json.loads(cfg)
s, out = call("/api/scan", body)
d = json.loads(out)
st = d["stats"]
print("POST /api/scan   ->", s, "| total:", st["total"], "pairs:", st["dup_pairs"],
      "reused:", st["reused"], "amount_ok:", st["amount_ok"])
# 4) 导出 CSV
s, csv = call("/api/export.csv?scope=dup")
txt = csv.decode("utf-8-sig")
print("GET /api/export.csv(dup) ->", s, "| 行数:", txt.count(chr(10)), "| 表头含'费用分类':", "费用分类" in txt)
