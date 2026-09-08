# Local Invoice Guardian（发票管家）

Windows 本地发票内容查重与费用分类工具。支持 PDF、JPG、PNG 等票据，不依赖文件名判断重复。

## 功能

- 将本次新发票与历史已使用发票按内容比对
- 识别发票号码、金额、日期和销售方
- 可选智谱 AI OCR，处理图片及损坏或无文本层的 PDF
- 按可维护的二级关键词归入一级费用分类
- 支持人工改类、使用状态、CSV 导出和复制归档

## 快速开始

1. （可跳过）未装 Python 时脚本会用 winget 自动安装；也可手动安装并勾选 `Add Python to PATH`。
2. 从 [Releases](https://github.com/onlyforchris/local-invoice-guardian/releases) 下载源码并解压。
3. 双击 `安装并启动.bat`：自动创建 `.venv`、优先用国内镜像装依赖，完成后自动启动；以后可双击 `启动发票管家.bat`。

程序只监听本机 `127.0.0.1:8765`。详细目录含义、分类维护、智谱 API Key 配置和常见问题见[使用说明](docs/使用说明.md)。

## 开发

```powershell
python -m pip install -r requirements.txt
python test_core.py
python app.py
```

## 注意

- 分类是财务复核建议，不代表允许报销、税前扣除或进项抵扣。
- 开启 AI OCR 后，相关票据页面会发送到智谱服务。
- 请勿在 Issue 中上传真实发票、API Key、税号、公司内部路径或个人信息。

MIT License。版本变化见 [CHANGELOG](CHANGELOG.md)。
