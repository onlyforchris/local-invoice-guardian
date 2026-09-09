# -*- coding: utf-8 -*-
"""核心查重与分类的最小回归检查。"""
import io
import urllib.error

import app
import update


def keys(fields, md5="same"):
    return {key for _level, key in app.fingerprint(fields, md5)}


def main():
    a = {"no": "12345678", "amount_cents": 1000}
    b = {"no": "12345678", "amount_cents": 1100}
    assert keys(a) & keys(b), "同发票号码、金额识别不一致时必须提示"
    assert "md5|same" in keys(a), "有结构化字段时也必须保留文件内容指纹"
    assert app.is_within(r"C:\used\a.pdf", r"C:\used")
    assert not app.is_within(r"C:\used_backup\a.pdf", r"C:\used")
    assert app.classify_text("项目名称：打印纸")[0] == "office"
    assert app.classify_text("项目名称：酒店住宿")[0] == "travel"
    assert app.classify_text("项目名称：停车费")[0] == "transport"
    assert app.classify_text("高德打车网约车服务")[0] == "transport"
    assert app.classify_text("员工下午茶餐饮")[0] == "benefit"
    assert app.classify_text("生产生活服务餐费")[0] == "benefit"
    assert app.classify_text("项目名称：休闲零食食品")[0] == "benefit"
    assert app.classify_text("项目名称：宴请礼品")[0] == "hospitality"
    assert app.classify_text("顺丰收派服务")[0] == "office"
    assert app.classify_text("网约车客运服务费")[0] == "transport"
    assert app.classify_text("92号车用乙醇")[0] == "transport"
    assert app.classify_text("人工智能技术服务")[0] == "service"
    assert app.classify_text("熟肉制品酱板鸭")[0] == "benefit"
    broken = "发票号码：\x002\x006\x003\x001\x007\x009\x000\x007\x001\x005\x000\x009\x000\x000\x000\x007\x002\x000\x003\x003\n2026^t09g\b07\n价税合计（小写）\x00¥\x001\x00.\x009\x006"
    fields = app.extract_fields(broken)
    assert fields["no"] == "26317907150900072033"
    assert fields["date"] == "2026-09-07"
    assert fields["amount_cents"] == 196
    assert app.extract_fields("价税合计（大写）：壹佰圆肆角伍分 （小写）：100.45")["amount_cents"] == 10045
    party = app.extract_fields(
        "名称: 上海亿流科技有限公司\n统一社会信用代码: 9131011259474644XJ\n"
        "名称: 杭州市西湖区国娣餐饮店\n统一社会信用代码: 92330106MA2GKHP698",
        company_names=["上海亿流科技有限公司"])
    assert party["seller"] == "杭州市西湖区国娣餐饮店"
    joined = app.extract_fields(
        "26332000007717763206\n2026年09月07日\n上海亿流科技有限公司\n"
        "9131011259474644XJ杭州市西湖区显光烧饼店\n92330106MA2BK14X8G",
        company_names=["上海亿流科技有限公司"])
    assert joined["seller"] == "杭州市西湖区显光烧饼店"
    compact = "上海亿流科技有限公司 上海⾦拱⻔⻝品有限公司\n9131011259474644XJ 913100006072048513"
    fields = app.extract_fields(compact, company_names=["上海亿流科技有限公司"])
    assert fields["seller"] == "上海金拱门食品有限公司"
    assert app.validate_categories(app.DEFAULT_CATEGORIES)
    assert update.version_key("v1.1.10") > update.version_key("1.1.9")
    assert "无效" in app.friendly_ocr_error(urllib.error.HTTPError("", 401, "", {}, None))
    assert "频率" in app.friendly_ocr_error(urllib.error.HTTPError("", 429, "", {}, None))

    # xlsx 分类汇总导出
    from openpyxl import load_workbook
    recs = [
        {"path": "a", "fname": "a.pdf", "folder": "F", "amount_cents": 1470,
         "date": "2026-08-02", "cat_label": "交通费", "seller": "s1",
         "is_used": False, "dups": []},
        {"path": "b", "fname": "b.pdf", "folder": "F", "amount_cents": 200,
         "date": "2026-08-01", "cat_label": "交通费", "seller": "s2",
         "is_used": False, "dups": []},
        {"path": "c", "fname": "c.pdf", "folder": "F", "amount_cents": 77700,
         "date": "2026-08-03", "cat_label": "差旅费", "seller": "s3",
         "is_used": True, "dups": []},
        {"path": "d", "fname": "d.pdf", "folder": "F", "amount_cents": None,
         "date": None, "cat_label": "交通费", "seller": "s4",
         "is_used": False, "dups": []},
    ]
    buf = app.export_xlsx(recs)
    wb = load_workbook(filename=io.BytesIO(buf))
    ws = wb["分类汇总"]
    assert ws.cell(1, 1).value == "差旅费", "列顺序须按分类目录（差旅费在交通费前）"
    assert ws.cell(1, 2).value == "交通费"
    assert ws.cell(2, 2).value == 2, "金额按日期升序：0.8-1 的 2 元在前"
    assert ws.cell(3, 2).value == 14.7
    assert ws.cell(2, 1).value == 777
    assert ws.cell(5, 1).value == "=SUM(A2:A3)", "合计行统一覆盖数据区（空单元格按0计）"
    assert ws.cell(5, 2).value == "=SUM(B2:B3)"
    assert ws.cell(1, 3).value == "总计"
    ws2 = wb["明细"]
    assert ws2.cell(2, 4).value == "s2"
    assert app.record_in_scope({"is_used": False, "dups": [{"is_used": True}]}, "reused")
    assert not app.record_in_scope({"is_used": True, "dups": [{"is_used": True}]}, "reused")
    assert app.record_in_scope({"is_used": True, "in_watch": True, "dups": []}, "new")
    assert not app.record_in_scope({"is_used": False, "in_watch": False, "dups": []}, "new")
    assert not app.record_in_scope({"is_used": False, "dups": []}, "dup")
    print("core checks: ok")


if __name__ == "__main__":
    main()
