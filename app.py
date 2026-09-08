# -*- coding: utf-8 -*-
"""
发票管家 Invoice Manager —— 本地发票内容级查重 + 报销分类桌面工具
================================================================
能力：
  1. 读取本地可配置文件夹（收集箱 / 已使用批次文件夹 / 归档目录）内的发票
  2. 解析发票正文：文本型 PDF 用 pypdf 直接提字；无文本层 PDF / jpg / png 走
     智谱 GLM-4V OCR（需 ZHIPUAI_API_KEY，未配置时自动降级并提示）
  3. 内容级查重：不依赖文件名。指纹 = (发票号码+金额) / (发票号码) / (销方+金额+日期) / 文件MD5
  4. 报销分类：13 类费用科目（关键词规则，发票正文+文件名仅作分类线索），可人工改分类并记忆
  5. 台账持久化(JSON)、导出 CSV、把发票复制提取到归档目录

用法：
  python app.py                 # 启动本地服务(127.0.0.1:8765)并自动开浏览器
  python app.py --port 9000 --no-browser
  python app.py --test <dir> [dir...]   # 命令行只读自测
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WORKBUDDY_PACKAGES = os.path.expanduser(r"~/.workbuddy/binaries/python/envs/site-packages")
if os.path.isdir(WORKBUDDY_PACKAGES):
    sys.path.insert(0, WORKBUDDY_PACKAGES)
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    import pypdfium2 as pdfium
    from PIL import Image
except Exception:
    pdfium = None
    Image = None

LEDGER = os.path.join(APP_DIR, "invoice_ledger.json")
CONFIG = os.path.join(APP_DIR, "config.json")
STATIC = os.path.join(APP_DIR, "index.html")
ENGINE_VER = 4  # 引擎版本；升级后旧台账自动失效重解析
APP_VERSION = "1.1.1"
INVOICE_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".webp"}
BUYER_DEFAULT = []

# ---------- 报销分类科目（13 类）----------
CATALOG = [
    {"id": "office", "label": "办公费", "note": "办公用品、打印纸、快递、饮用水、绿植"},
    {"id": "travel", "label": "差旅费", "note": "机票、火车票、住宿、打车、订票手续费"},
    {"id": "transport", "label": "交通费", "note": "网约车、加油、停车、过路、租车"},
    {"id": "communication", "label": "通讯费", "note": "办公电话、宽带、通信服务"},
    {"id": "hospitality", "label": "业务招待费", "note": "餐饮招待、茶叶、礼品、食品"},
    {"id": "meeting", "label": "会议费", "note": "场地、资料"},
    {"id": "training", "label": "培训费", "note": "培训、报名费"},
    {"id": "advertising", "label": "广告宣传费", "note": "广告服务费、制作费、推广费"},
    {"id": "service", "label": "服务费", "note": "技术服务费、招聘费"},
    {"id": "rd", "label": "研发费用", "note": "专利/软著、研发设备、认证检测"},
    {"id": "property", "label": "房租物业水电", "note": "租赁、物业、水电"},
    {"id": "benefit", "label": "人事福利", "note": "团建、下午茶、餐饮"},
    {"id": "other", "label": "其他/待分类", "note": "建议人工补充规则"},
]
CAT_IDS = [c["id"] for c in CATALOG]

# 分类关键词规则（有序，先命中更具体；文本=文件名+销方+品名+正文片段）
RULES = [
    ("office", ["办公用品", "打印纸", "快递", "饮用水", "绿植", "文具", "耗材", "硒鼓", "墨盒", "a4纸"]),
    ("travel", ["机票", "火车票", "住宿", "打车", "订票手续费", "行程单", "高铁", "动车", "酒店", "宾馆"]),
    ("transport", ["网约车", "加油", "停车", "过路", "租车", "滴滴", "出租车", "通行费", "代驾"]),
    ("communication", ["办公电话", "宽带", "通信服务", "中国移动", "中国联通", "中国电信", "话费"]),
    ("hospitality", ["餐饮招待", "业务招待", "宴请", "茶叶", "礼品", "食品"]),
    ("meeting", ["会议场地", "会议资料", "会议费"]),
    ("training", ["培训", "报名费", "课程", "训练营", "考试费"]),
    ("advertising", ["广告服务费", "制作费", "推广费", "广告宣传"]),
    ("service", ["技术服务费", "招聘费", "软件服务", "云服务", "咨询服务"]),
    ("rd", ["专利", "软著", "软件著作权", "研发设备", "认证检测", "认证费", "检测费"]),
    ("property", ["房屋租赁", "租赁费", "物业", "水费", "电费", "水电"]),
    ("benefit", ["团建", "下午茶", "员工餐", "餐饮", "外卖", "咖啡", "奶茶"]),
]

DEFAULT_CATEGORIES = [
    {**c, "keywords": next((list(kws) for cid, kws in RULES if cid == c["id"]), [])}
    for c in CATALOG
]
STATE_LOCK = threading.RLock()

COMPANY_RE = re.compile(
    r"[\u4e00-\u9fa5A-Za-z0-9（）()·]+?"
    r"(?:有限公司|有限责任公司|股份有限公司|个体工商户|合伙企业|工作室)")


def get_categories(cfg=None):
    cfg = load_config() if cfg is None else cfg
    cats = cfg.get("categories")
    return cats if isinstance(cats, list) and cats else DEFAULT_CATEGORIES


def classify_text(text, categories=None):
    t = (text or "").lower()
    t = re.sub(r"\s+", "", t)
    if not t:
        return "other", "无内容"
    matches = []
    for order, cat in enumerate(categories or DEFAULT_CATEGORIES):
        for k in cat.get("keywords", []):
            if k in t:
                matches.append((len(k), -order, cat["id"], k))
    if matches:
        _length, _order, cid, keyword = max(matches)
        return cid, keyword
    return "other", "未命中规则"


# ---------- 字段归一化 ----------
def _strip_ws(s):
    return re.sub(r"\s+", "", s or "")


def norm_amount_cents(raw):
    if raw is None:
        return None
    try:
        return int(Decimal(re.sub(r"[^\d.]", "", str(raw))) * 100)
    except Exception:
        return None


def _valid_date(y, m, d):
    try:
        y, m, d = int(y), int(m), int(d)
        return 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31
    except Exception:
        return False


def norm_date(raw):
    if not raw:
        return None
    m = re.search(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", str(raw))
    if m and _valid_date(*m.groups()):
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
    m = re.search(r"(\d{4})(\d{2})(\d{2})", str(raw))
    if m and _valid_date(*m.groups()):
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
    return None


# ---------- 从正文提取字段（PDF 文本与 OCR 文本共用）----------
def _companies(text):
    out = []
    for c in COMPANY_RE.findall(text or ""):
        c = c.strip()
        c = re.sub(r"^[\s:：]+", "", c)
        if len(re.findall(r"[\u4e00-\u9fa5]", c)) >= 2 and c not in out:
            out.append(c)
    return out


def extract_fields(text, fname="", company_names=None):
    """返回字段 dict。金额以「价税合计（小写）」为准。"""
    t = text or ""
    t2 = re.sub(r"(\d),(?=\d{3})", r"\1", t)
    f = {"no": None, "code": None, "date": None, "amount_cents": None,
         "seller": None, "buyer": None, "kind": "其他", "items": []}

    m = re.search(r"发票号码[:：\s]*([0-9]{8,20})", t2)
    if not m:
        m = re.search(r"([0-9]{20})", t2)
    f["no"] = m.group(1) if m else None
    m = re.search(r"发票代码[:：\s]*([0-9]{10,12})", t2)
    f["code"] = m.group(1) if m else None

    # 日期：优先“开票日期”标签，其次靠近发票号码/价税合计位置的独立日期
    m = re.search(r"开票日期[^0-9]{0,8}([0-9]{4}[年\-/.]\d{1,2}[月\-/.]\d{1,2})", t2)
    if not m:
        m = re.search(r"开票日期[^0-9]{0,8}(\d{8})", t2)
    if m:
        f["date"] = norm_date(m.group(1))
    if not f["date"]:
        anchor = t2.find(f["no"]) if f["no"] else t2.find("价税合计")
        if anchor < 0:
            anchor = 0
        dates = list(re.finditer(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", t2))
        if dates:
            dates = sorted(dates, key=lambda x: abs(x.start() - anchor))
            f["date"] = norm_date(dates[0].group(0))

    # 金额：价税合计（小写）→ （小写）→ 合计 → 最大 ¥
    amt = None
    for pat in (r"价税合计[^¥￥]{0,24}[¥￥]\s*([0-9]+\.\d{2})",
                r"[（(]\s*小写\s*[)）]\s*[¥￥]?\s*([0-9]+\.\d{2})",
                r"(?:合计|合计金额)[^0-9¥￥]{0,12}([0-9]+\.\d{2})"):
        m = re.search(pat, t2)
        if m:
            amt = m.group(1)
            break
    if amt is None:
        nums = re.findall(r"[¥￥]\s*([0-9]+\.\d{2})", t2)
        if nums:
            amt = max(nums, key=lambda x: Decimal(x))
    f["amount_cents"] = norm_amount_cents(amt)

    # 购销双方：公司名识别，购方=本公司（config 可改）
    buyers = company_names or BUYER_DEFAULT
    comps = _companies(t2)
    if comps:
        b = next((c for c in comps if any(bk in c for bk in buyers)), comps[0])
        s = next((c for c in comps if c != b), None)
        f["buyer"], f["seller"] = b, s

    # 类型
    if "数电" in t2:
        f["kind"] = "数电票"
    elif "增值税专用发票" in t2:
        f["kind"] = "增值税专用发票"
    elif "增值税普通发票" in t2 or "电子发票（普通" in t2:
        f["kind"] = "增值税普通发票"
    elif "行程单" in t2:
        f["kind"] = "行程单"
    elif "通行费" in t2:
        f["kind"] = "通行费发票"
    elif "出租车" in t2:
        f["kind"] = "出租车票"

    # 品名（项目名称表格首行明细）+ 服务编码（如 *交通运输服务*客运服务费）
    items = []
    m = re.search(r"项目名称[^\n]{0,12}\n", t2)
    if m:
        seg = t2[m.end():m.end() + 400]
        for line in seg.splitlines():
            line = line.strip()
            if not line or re.search(r"规格型号|单位|数量|单价|金额|税率|税额|价税合计|备注|合计", line):
                break
            if len(line) > 3:
                items.append(line[:80])
    f["items"] = items[:6]
    f["svc"] = re.findall(r"\*[^*\n]{1,30}\*([^*\n]{2,40})", t2)[:4]

    return f


# ---------- 文件与 OCR ----------
def file_md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def zhipu_key():
    return os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("ZAI_API_KEY") or ""


def ocr_b64(b64, mime, model="glm-4v-flash", timeout=60):
    """把 base64 图片发到智谱视觉模型，返回识别出的纯文本。"""
    key = zhipu_key()
    if not key:
        raise RuntimeError("未配置 ZHIPUAI_API_KEY")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, b64)}},
                {"type": "text",
                 "text": "请完整识别这张发票/票据上的全部文字，按原文输出纯文本。务必保留「发票号码："
                         "xxx」「开票日期：xxxx年x月x日」「价税合计（小写）¥xx.xx」「销售方名称」「购买方名称」"
                         "「项目名称」下的明细等关键内容。不要解释、不要总结。"},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"] or ""


def ocr_image_file(path, model="glm-4v-flash"):
    ext = os.path.splitext(path)[1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "bmp": "image/bmp", "webp": "image/webp"}.get(ext.lstrip("."), "image/jpeg")
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return ocr_b64(b64, mime, model)


def render_pdf_pages(path, scale=2.2, max_pages=4):
    """无文本层 PDF -> 渲染成 PNG -> base64 列表（pypdfium2）。"""
    if pdfium is None:
        return []
    doc = pdfium.PdfDocument(path)
    out = []
    try:
        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            bmp = page.render(scale=scale)
            img = bmp.to_pil()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            out.append(base64.b64encode(buf.getvalue()).decode())
    finally:
        doc.close()
    return out


def parse_file(path, ocr_enabled=True, ocr_model="glm-4v-flash", company_names=None):
    """解析单张发票 -> (fields, warn)。warn 非空表示有降级/提示。"""
    ext = os.path.splitext(path)[1].lower()
    warn = None
    text = ""
    if ext == ".pdf":
        if PdfReader is not None:
            try:
                text = "".join((p.extract_text() or "") for p in PdfReader(path).pages)
            except Exception as e:
                warn = "PDF解析异常:%s" % e
        # 文本过少(疑无文本层)时尝试渲染 OCR
        if len(re.sub(r"\s", "", text or "")) < 40 and ocr_enabled and zhipu_key():
            try:
                pages = render_pdf_pages(path)
                chunks = []
                for b64 in pages:
                    try:
                        chunks.append(ocr_b64(b64, "image/png", ocr_model))
                    except Exception as e:
                        warn = "PDF页OCR失败:%s" % e
                if chunks:
                    text = "\n".join(chunks)
                    warn = "PDF经渲染OCR识别"
            except Exception as e:
                warn = "PDF渲染失败:%s" % e
        if not warn and len(re.sub(r"\s", "", text or "")) < 40:
            warn = "PDF无文本层且未启用OCR(需配置ZHIPUAI_API_KEY)"
    else:  # 图片
        if ocr_enabled and zhipu_key():
            try:
                text = ocr_image_file(path, ocr_model)
                warn = None if text.strip() else "OCR返回为空"
            except Exception as e:
                warn = "OCR失败:%s" % e
        else:
            warn = "图片发票未启用OCR(需配置ZHIPUAI_API_KEY)"
    fields = extract_fields(text or "", os.path.basename(path), company_names)
    fields["class_text"] = (text or "")[:6000]
    fields["ocr"] = bool(ext != ".pdf" or (warn and "OCR" in (warn or "")))
    return fields, warn


def fingerprint(fields, md5hex):
    keys = [("exact", "md5|%s" % md5hex)]
    if fields.get("no") and fields.get("amount_cents"):
        keys.append(("high", "no+amt|%s|%s" % (fields["no"], fields["amount_cents"])))
    if fields.get("no"):
        if fields.get("code"):
            keys.append(("high", "code+no|%s|%s" % (fields["code"], fields["no"])))
        else:
            keys.append(("mid", "no|%s" % fields["no"]))
    if fields.get("seller") and fields.get("amount_cents") and fields.get("date"):
        keys.append(("low", "sel+amt+date|%s|%s|%s" % (
            _strip_ws(fields["seller"]).lower(), fields["amount_cents"], fields["date"])))
    return keys


# ---------- 台账 ----------
def load_ledger():
    if os.path.exists(LEDGER):
        try:
            return json.load(open(LEDGER, encoding="utf-8"))
        except Exception:
            return {"version": 2, "records": {}}
    return {"version": 2, "records": {}}


def save_ledger(led):
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER)


def load_config():
    if os.path.exists(CONFIG):
        try:
            return json.load(open(CONFIG, encoding="utf-8"))
        except Exception:
            pass
    return {"watch_dirs": [], "used_dirs": [], "archive_dir": "",
            "ocr_model": "glm-4v-flash", "company_names": BUYER_DEFAULT}


def save_config(cfg):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, CONFIG)


def is_within(path, folder):
    try:
        return os.path.commonpath((os.path.abspath(path), os.path.abspath(folder))) == os.path.abspath(folder)
    except (ValueError, OSError):
        return False


def records_in_dirs(led, dirs):
    return [r for r in led.get("records", {}).values()
            if any(is_within(r["path"], d) for d in dirs)]


def validate_categories(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise ValueError("分类数量应为 1-50 个")
    out, seen = [], set()
    for i, cat in enumerate(raw):
        cid = str(cat.get("id") or "").strip()
        label = str(cat.get("label") or "").strip()
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", cid) or cid in seen or not label:
            raise ValueError("第 %d 个分类的标识或名称无效" % (i + 1))
        kws = [str(x).strip() for x in cat.get("keywords", []) if str(x).strip()]
        out.append({"id": cid, "label": label[:50],
                    "note": str(cat.get("note") or "").strip()[:120],
                    "keywords": list(dict.fromkeys(kws))[:100]})
        seen.add(cid)
    if "other" not in seen:
        raise ValueError("必须保留 other（其他/待分类）")
    return out


def iter_invoice_files(dirs):
    seen = set()
    for d in dirs or []:
        if not d or not os.path.isdir(d):
            continue
        for root, _subs, files in os.walk(d):
            if any(seg.startswith(".") for seg in root.split(os.sep)):
                continue
            for fn in files:
                if os.path.splitext(fn)[1].lower() in INVOICE_EXTS:
                    p = os.path.normpath(os.path.join(root, fn))
                    if p not in seen:
                        seen.add(p)
                        yield p


def build_scan(watch_dirs, used_dirs, ocr_enabled, ocr_model):
    """扫描并增量更新台账（只读文件内容，绝不删除/移动）。"""
    led = load_ledger()
    if led.get("version") != ENGINE_VER:
        led = {"version": ENGINE_VER, "records": {}}
    all_dirs = list(dict.fromkeys(list(watch_dirs or []) + list(used_dirs or [])))
    used_set = {os.path.normpath(d) for d in (used_dirs or []) if d and os.path.isdir(d)}
    if os.path.exists(CONFIG):
        led_cfg = json.load(open(CONFIG, encoding="utf-8"))
    else:
        led_cfg = {}
    buyers = led_cfg.get("company_names") or BUYER_DEFAULT
    categories = get_categories(led_cfg)
    parse_sig = hashlib.sha256(json.dumps({
        "engine": ENGINE_VER, "ocr": bool(ocr_enabled), "ocr_model": ocr_model,
        "ocr_key": bool(zhipu_key()), "buyers": buyers,
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    cat_sig = hashlib.sha256(json.dumps(categories, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    # 1) 增量解析
    for p in iter_invoice_files(all_dirs):
        st = os.stat(p)
        rec = led["records"].get(p)
        unchanged = rec and rec.get("mtime") == st.st_mtime and rec.get("size") == st.st_size
        if unchanged and rec.get("parse_sig") == parse_sig:
            if rec.get("cat_rule") == "人工":
                rec["cat_label"] = next((c["label"] for c in categories
                                          if c["id"] == rec.get("cat_id")), "其他/待分类")
            elif rec.get("cat_sig") != cat_sig:
                cid, rule = classify_text(rec.get("cls_text", ""), categories)
                rec.update(cat_id=cid, cat_rule=rule,
                           cat_label=next((c["label"] for c in categories if c["id"] == cid), cid),
                           cat_sig=cat_sig)
            continue
        fields, warn = parse_file(p, ocr_enabled, ocr_model, buyers)
        md5hex = file_md5(p)
        fp = fingerprint(fields, md5hex)
        cls_text = os.path.basename(p) + "|" + (fields.get("seller") or "") + "|" + \
                   " ".join(fields.get("items") or []) + "|" + \
                   " ".join(fields.get("svc") or []) + "|" + (fields.get("kind") or "") + "|" + \
                   fields.get("class_text", "")
        rec = {
            "path": p, "folder": os.path.basename(os.path.dirname(p)),
            "fname": os.path.basename(p), "size": st.st_size, "mtime": st.st_mtime,
            "md5": md5hex,
            "no": fields.get("no"), "code": fields.get("code"),
            "date": fields.get("date"), "amount_cents": fields.get("amount_cents"),
            "seller": fields.get("seller"), "buyer": fields.get("buyer"),
            "kind": fields.get("kind"), "items": fields.get("items"),
            "svc": fields.get("svc"),
            "ocr": fields.get("ocr", False), "warn": warn,
            "fp": fp, "cls_text": cls_text[:6000], "parse_sig": parse_sig, "cat_sig": cat_sig,
            "cat_id": rec.get("cat_id") if rec and rec.get("cat_rule") == "人工" else None,
            "cat_label": rec.get("cat_label") if rec and rec.get("cat_rule") == "人工" else None,
            "cat_rule": rec.get("cat_rule") if rec and rec.get("cat_rule") == "人工" else None,
            "used_override": rec.get("used_override", False) if rec else False,
            "used_override_set": rec.get("used_override_set", False) if rec else False,
            "first_seen": rec.get("first_seen", time.time()) if rec else time.time(),
            "updated": time.time(),
        }
        cid, rule = classify_text(rec["cls_text"], categories)
        if rec["cat_id"] is None:
            rec["cat_id"], rec["cat_rule"] = cid, rule
            rec["cat_label"] = next((c["label"] for c in categories if c["id"] == cid), cid)
        led["records"][p] = rec

    # 2) 清理已从配置目录消失的记录
    cfg_prefixes = tuple(os.path.normpath(d) for d in all_dirs if d)
    if cfg_prefixes:
        for p in list(led["records"]):
            if any(is_within(p, d) for d in cfg_prefixes) and not os.path.exists(p):
                del led["records"][p]

    # 3) 内容查重（同源不判重：同一物理文件只有一条记录）
    recs = records_in_dirs(led, all_dirs)
    for r in recs:
        folder_used = any(is_within(r["path"], d) for d in used_set)
        r["is_used"] = bool(r.get("used_override")) if r.get("used_override_set") else folder_used
    idx = {}
    for r in recs:
        for w, k in r["fp"]:
            idx.setdefault(k, []).append(r)
    for r in recs:
        r["dups"] = []
        seenp = set()
        for w, k in r["fp"]:
            basis = ("文件内容完全一致" if k.startswith("md5|") else
                     "发票代码+号码一致" if k.startswith("code+no|") else
                     "发票号+金额一致" if k.startswith("no+amt|") else
                     "发票号码一致" if k.startswith("no|") else
                     "销方+金额+日期一致" if k.startswith("sel+amt+date|") else w)
            for o in idx.get(k, []):
                if o["path"] != r["path"] and o["path"] not in seenp:
                    seenp.add(o["path"])
                    r["dups"].append({"level": "高危" if w != "low" else "疑似", "basis": basis,
                                      "fname": o["fname"], "folder": o["folder"],
                                      "path": o["path"], "no": o.get("no"),
                                      "amount": o.get("amount_cents"), "is_used": o["is_used"]})
    save_ledger(led)
    return led, used_set, recs


# ---------- CSV ----------
def csv_escape(v):
    v = "" if v is None else str(v)
    if any(ch in v for ch in (",", '"', "\n")):
        v = '"' + v.replace('"', '""') + '"'
    return v


def export_csv(recs, scope):
    head = ["文件名", "所在文件夹", "金额(元)", "开票日期", "发票号码", "发票代码",
            "销售方", "费用分类", "分类依据", "状态", "重复提示", "OCR/提示", "文件路径"]
    lines = [",".join(head)]
    for r in recs:
        used = "已使用" if r["is_used"] else "待使用"
        dup = "；".join("%s[%s/%s]" % (d["basis"], d["folder"], d["fname"])
                        for d in r["dups"]) or ""
        if (scope == "used" and not r["is_used"]) or \
           (scope == "dup" and not r["dups"]) or \
           (scope == "reused" and (r["is_used"] or not any(d.get("is_used") for d in r["dups"]))) or \
           (scope == "new" and r["is_used"]):
            continue
        row = [r["fname"], r["folder"], (r["amount_cents"] or 0) / 100,
               r.get("date") or "", r.get("no") or "", r.get("code") or "",
               r.get("seller") or "", r.get("cat_label") or "", r.get("cat_rule") or "",
               used, dup, r.get("warn") or "", r["path"]]
        lines.append(",".join(csv_escape(x) for x in row))
    return "\ufeff" + "\n".join(lines)


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        ln = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            if os.path.exists(STATIC):
                html = open(STATIC, encoding="utf-8").read().replace("{{APP_VERSION}}", APP_VERSION)
                return self._send(200, html,
                                  "text/html; charset=utf-8")
            return self._send(404, "缺少 index.html")
        if u.path == "/api/config":
            return self._send(200, json.dumps(load_config()))
        if u.path == "/api/categories":
            return self._send(200, json.dumps(get_categories(), ensure_ascii=False))
        if u.path == "/api/folders":
            desk = os.path.join(os.path.expanduser("~"), "Desktop")
            found = []
            if os.path.isdir(desk):
                for d in sorted(os.listdir(desk)):
                    full = os.path.join(desk, d)
                    if os.path.isdir(full) and (re.match(r"^20\d{4}", d) or "发票" in d
                                                or "报销" in d or "归档" in d):
                        found.append(full)
            return self._send(200, json.dumps({"desktop": desk, "folders": found}))
        if u.path == "/api/export.csv":
            q = parse_qs(u.query)
            scope = (q.get("scope") or ["all"])[0]
            cfg = load_config()
            led = load_ledger()
            used_set = {os.path.normpath(d) for d in cfg.get("used_dirs", []) if d and os.path.isdir(d)}
            dirs = list(cfg.get("watch_dirs", [])) + list(cfg.get("used_dirs", []))
            recs = records_in_dirs(led, dirs)
            for r in recs:
                folder_used = any(is_within(r["path"], d) for d in used_set)
                r["is_used"] = bool(r.get("used_override")) if r.get("used_override_set") else folder_used
            return self._send(200, export_csv(recs, scope), "text/csv; charset=utf-8")
        self._send(404, "{}")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/categories":
            try:
                cats = validate_categories(self._read_json().get("categories"))
                with STATE_LOCK:
                    cfg = load_config()
                    cfg["categories"] = cats
                    save_config(cfg)
                return self._send(200, json.dumps({"ok": True, "categories": cats}, ensure_ascii=False))
            except (ValueError, TypeError) as e:
                return self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False))
        if u.path == "/api/scan":
            body = self._read_json()
            watch = body.get("watch_dirs") or []
            used = body.get("used_dirs") or []
            ocr = bool(body.get("ocr_enabled", True))
            model = body.get("ocr_model") or "glm-4v-flash"
            cfg = load_config()
            cfg.update({"watch_dirs": watch, "used_dirs": used,
                        "ocr_model": model, "ocr_enabled": ocr,
                        "archive_dir": body.get("archive_dir") or ""})
            if body.get("company_names"):
                cfg["company_names"] = body["company_names"]
            with STATE_LOCK:
                save_config(cfg)
                led, used_set, recs = build_scan(watch, used, ocr, model)
            catalog = get_categories(cfg)
            cats = {}
            for c in catalog:
                cats[c["id"]] = {"label": c["label"], "note": c["note"], "count": 0, "sum": 0.0}
            n_dup, n_used, n_warn, n_amt = 0, 0, 0, 0
            for r in recs:
                if r["is_used"]:
                    n_used += 1
                if r["dups"]:
                    n_dup += 1
                if r.get("warn"):
                    n_warn += 1
                if r.get("amount_cents") is not None:
                    n_amt += 1
                cid = r.get("cat_id") or "other"
                if cid in cats:
                    cats[cid]["count"] += 1
                    cats[cid]["sum"] += (r["amount_cents"] or 0) / 100
            recs.sort(key=lambda r: (-1 if r["dups"] else 0, -1 if r["is_used"] else 0,
                                     -(r["amount_cents"] or 0)))
            pairs = {tuple(sorted((r["path"], d["path"]))) for r in recs for d in r["dups"]}
            reused = sum(not r["is_used"] and any(d.get("is_used") for d in r["dups"]) for r in recs)
            return self._send(200, json.dumps({
                "records": recs, "categories": cats,
                "stats": {"total": len(recs), "dup": n_dup, "used": n_used,
                          "warn": n_warn, "amount_ok": n_amt,
                          "ocr_key": bool(zhipu_key()), "dup_pairs": len(pairs),
                          "reused": reused},
                "config": cfg,
            }, ensure_ascii=False))
        if u.path == "/api/override":
            body = self._read_json()
            path = body.get("path")
            with STATE_LOCK:
                led = load_ledger()
                if path not in led["records"]:
                    return self._send(404, json.dumps({"error": "发票记录不存在"}, ensure_ascii=False))
                r = led["records"][path]
                if "cat_id" in body:
                    catalog = get_categories()
                    if body["cat_id"] not in {c["id"] for c in catalog}:
                        return self._send(400, json.dumps({"error": "分类不存在"}, ensure_ascii=False))
                    r["cat_id"] = body["cat_id"]
                    r["cat_label"] = next((c["label"] for c in catalog
                                           if c["id"] == body["cat_id"]), body["cat_id"])
                    r["cat_rule"] = "人工"
                if "used" in body:
                    r["used_override"] = bool(body["used"])
                    r["used_override_set"] = True
                save_ledger(led)
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/extract":
            import shutil
            body = self._read_json()
            paths = body.get("paths") or []
            target = body.get("target_dir") or ""
            if not target or not os.path.isdir(target):
                return self._send(400, json.dumps({"error": "归档目录不存在或未填写"}))
            cfg = load_config()
            allowed = {r["path"] for r in records_in_dirs(
                load_ledger(), list(cfg.get("watch_dirs", [])) + list(cfg.get("used_dirs", [])))}
            copied, skipped = [], []
            for p in paths:
                if p in allowed and os.path.isfile(p):
                    dst = os.path.join(target, os.path.basename(p))
                    if os.path.exists(dst):
                        skipped.append(dst)
                    else:
                        shutil.copy2(p, dst)
                        copied.append(dst)
            return self._send(200, json.dumps({"copied": copied, "skipped": skipped}, ensure_ascii=False))
        self._send(404, "{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--test", nargs="*", help="命令行只读自测目录")
    a = ap.parse_args()
    if a.test is not None:
        cfg = load_config()
        dirs = a.test or cfg.get("watch_dirs") or []
        led, used_set, recs = build_scan(dirs, cfg.get("used_dirs") or [], True,
                                         cfg.get("ocr_model") or "glm-4v-flash")
        for r in sorted(recs, key=lambda r: (r["folder"], r["fname"])):
            dup = ("重复[%s]" % ", ".join("%s/%s:%s" % (d["folder"], d["fname"], d["basis"])
                                          for d in r["dups"])) if r["dups"] else ""
            print("%-6s %-24s %8s %-10s %-20s %-14s %-20s %s%s" % (
                r["folder"], r["fname"][:24],
                "%.2f" % ((r["amount_cents"] or 0) / 100) if r["amount_cents"] is not None else "-",
                r.get("date") or "-", (r.get("no") or "-")[:20],
                (r.get("cat_label") or "")[:14], (r.get("seller") or "-")[:20],
                dup, (" | " + r["warn"]) if r.get("warn") else ""))
        print("\n合计 %d 张 | 重复风险 %d | 已使用 %d | OCR可用=%s | 金额已解析 %d" % (
            len(recs), sum(1 for x in recs if x["dups"]),
            sum(1 for x in recs if x["is_used"]), bool(zhipu_key()),
            sum(1 for x in recs if x.get("amount_cents") is not None)))
        return 0
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d" % a.port
    print("发票管家已启动: %s  (Ctrl+C 退出)" % url)
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
