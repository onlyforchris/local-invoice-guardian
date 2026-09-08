# -*- coding: utf-8 -*-
"""核心查重与分类的最小回归检查。"""
import app


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
    assert app.classify_text("项目名称：休闲零食食品")[0] == "benefit"
    assert app.classify_text("项目名称：宴请礼品")[0] == "hospitality"
    broken = "发票号码：\x002\x006\x003\x001\x007\x009\x000\x007\x001\x005\x000\x009\x000\x000\x000\x007\x002\x000\x003\x003\n2026^t09g\b07\n价税合计（小写）\x00¥\x001\x00.\x009\x006"
    fields = app.extract_fields(broken)
    assert fields["no"] == "26317907150900072033"
    assert fields["date"] == "2026-09-07"
    assert fields["amount_cents"] == 196
    assert app.validate_categories(app.DEFAULT_CATEGORIES)
    print("core checks: ok")


if __name__ == "__main__":
    main()
