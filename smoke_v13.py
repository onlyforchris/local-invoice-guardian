# -*- coding: utf-8 -*-
"""v1.3.0 冒烟：备份/恢复、历史导入、永久库、结案、审核底稿。"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import HTTPServer

import app

PORT = 8791
BASE = "http://127.0.0.1:%d" % PORT
ok = []


def check(name, cond, extra=""):
    ok.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + name + ((" -> " + str(extra)) if extra else ""))


def call(path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return raw


def get_raw(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read()


def main():
    tmp = tempfile.mkdtemp(prefix="inv-smoke-")
    # 隔离：所有数据文件改写到临时目录，绝不触碰用户真实台账/配置
    app.LEDGER = os.path.join(tmp, "invoice_ledger.json")
    app.USED_LEDGER = os.path.join(tmp, "used_ledger.json")
    app.CONFIG = os.path.join(tmp, "config.json")
    app.BACKUP_DIR = os.path.join(tmp, "backups")
    # 造一个最小 PDF（ASCII 内容，仅验证解析链路不崩）
    pdf = os.path.join(tmp, "sample.pdf")
    body = (b"BT /F1 12 Tf 50 700 Td (INVOICE 24312000000112345678) Tj ET")
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b""
    ) + (b"4 0 obj<</Length %d>>stream\n" % len(body)) + body + (
        b"\nendstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n")
    open(pdf, "wb").write(pdf_bytes)

    srv = HTTPServer(("127.0.0.1", PORT), app.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.4)
    try:
        print("[1] 基础接口")
        check("首页可访问", "发票管家".encode("utf-8") in get_raw("/"))
        st = call("/api/ledger-status")
        check("台账状态接口", "used_count" in st and "backups" in st, st.get("used_count"))

        print("[2] N3 历史台账导入（冷启动）")
        csv_text = "发票号码,开票日期,金额,销售方\n24312000000112345678,2026-08-01,100.45,某某餐饮店\n" \
                   "24312000000112345679,2026-08-02,200.00,某某酒店\n"
        r = call("/api/import-history", {"csv": csv_text, "batch": "2026-08"})
        check("导入成功", r.get("ok") and r.get("added") == 2, r.get("message"))
        ul = call("/api/used-ledger")
        check("永久库已写入", ul.get("total") == 2, ul.get("total"))
        r2 = call("/api/import-history", {"csv": csv_text, "batch": "2026-08"})
        check("重复导入自动跳过", r2.get("added") == 0, r2.get("message"))

        print("[3] N2 永久库脱离文件 + 查重注入")
        app.save_config({"watch_dirs": [tmp], "used_dirs": [], "archive_dir": "",
                         "company_names": ["上海亿流"]})
        led, _u, recs = app.build_scan([tmp], [], False, "glm-4v-flash")
        check("扫描出记录", len(recs) == 1, len(recs))
        rec = recs[0]
        check("记录含校验字段", "check_issues" in rec and "buyer_status" in rec, rec.get("buyer_status"))
        check("记录含查验字段", rec.get("verify_status") == "未查验")

        print("[4] T1 台账备份")
        app.save_ledger(app.load_ledger())  # 台账已存在，再次写入前应先滚动备份
        baks = [f for f in os.listdir(app.BACKUP_DIR)] if os.path.isdir(app.BACKUP_DIR) else []
        check("已生成备份文件", len(baks) >= 1, baks[:2])
        # 损坏保护：写入坏文件后不得被静默当成空台账
        open(app.LEDGER, "w", encoding="utf-8").write("{ broken json")
        led_bad = app.load_ledger()
        check("损坏时登记状态而非静默清空", bool(app.LEDGER_STATUS.get("error")), app.LEDGER_STATUS["error"])
        check("损坏现场已留档", any("corrupt" in f for f in os.listdir(app.BACKUP_DIR)))
        recovered = app.restore_ledger(baks[0] if baks else "x.bak")
        check("可从备份还原", recovered >= 0 and app.LEDGER_STATUS.get("error") is None, recovered)

        print("[5] N1 结案入库 + 归档")
        arc = os.path.join(tmp, "archive")
        os.makedirs(arc, exist_ok=True)
        app.save_config({"watch_dirs": [tmp], "used_dirs": [], "archive_dir": arc,
                         "company_names": ["上海亿流"]})
        cb = call("/api/close-batch", {"paths": [pdf], "batch": "2026-09", "archive": True})
        check("结案成功", cb.get("ok") and cb.get("closed") == 1, cb)
        check("归档文件已生成", len(cb.get("copied") or []) == 1, cb.get("copied"))
        check("无主键票被显式标记", cb.get("no_key") == ["sample.pdf"], cb.get("no_key"))
        ul2 = call("/api/used-ledger")
        check("已报销库增长", ul2.get("total") >= 2, ul2.get("total"))

        print("[6] 永久库幽灵条目：原文件不在也能判重")
        no, cents = "24312000000112345678", 10045
        app.used_ledger_add([{"no": no, "code": None, "amount_cents": cents,
                              "date": "2026-07-01", "seller": "某某餐饮店",
                              "fname": "历史票.pdf", "path": "D:/elsewhere/历史票.pdf"}], "2026-07")
        st = os.stat(pdf)
        sig = hashlib.sha256(json.dumps(
            {"engine": app.ENGINE_VER, "ocr": False, "ocr_model": "glm-4v-flash",
             "ocr_key": bool(app.zhipu_key()), "buyers": ["上海亿流"]},
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        led = app.load_ledger()
        led["records"][pdf] = {
            "path": pdf, "folder": os.path.basename(tmp), "fname": "sample.pdf",
            "size": st.st_size, "mtime": st.st_mtime, "md5": app.file_md5(pdf),
            "no": no, "code": None, "date": "2026-07-01", "amount_cents": cents,
            "seller": "某某餐饮店", "buyer": "上海亿流科技有限公司", "kind": "增值税普通发票",
            "items": [], "svc": [], "ocr": False, "warn": None,
            "fp": app.fingerprint({"no": no, "amount_cents": cents}, app.file_md5(pdf)),
            "cls_text": "", "parse_sig": sig, "cat_sig": sig,
            "cat_id": "other", "cat_label": "其他/待分类", "cat_rule": "未命中规则",
            "used_override": False, "used_override_set": False,
            "verify_status": "未查验", "reject_reason": "", "closed": False,
            "first_seen": time.time(), "updated": time.time()}
        app.save_ledger(led)
        _l, _u, recs2 = app.build_scan([tmp], [], False, "glm-4v-flash")
        hits = [d for r in recs2 for d in (r.get("dups") or []) if d.get("ghost")]
        check("永久库幽灵条目被判为重复", len(hits) == 1, hits[:1])
        check("幽灵条目标注为已报销", bool(hits and hits[0].get("is_used")))

        print("[6b] 同主键重复结案不重复入库")
        total_before = call("/api/used-ledger").get("total")
        cb2 = call("/api/close-batch", {"paths": [pdf], "batch": "2026-09"})
        total_after = call("/api/used-ledger").get("total")
        check("重复结案幂等", cb2.get("added") == 0 and total_after == total_before,
              "%s -> %s" % (total_before, total_after))

        print("[7] 审核底稿导出")
        data = get_raw("/api/export.worksheet")
        check("底稿为 xlsx", data[:2] == b"PK", len(data))

        print("[8] 异常处理")
        try:
            call("/api/restore-ledger", {"name": "../config.json"})
            check("路径穿越被拒绝", False)
        except Exception as e:
            check("路径穿越被拒绝", "400" in str(e) or "不存在" in str(e))
        try:
            call("/api/close-batch", {"paths": ["nope.pdf"]})
            check("空结案被拒绝", False)
        except Exception as e:
            check("空结案被拒绝", "400" in str(e))
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n结果：%d/%d 通过" % (sum(ok), len(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
