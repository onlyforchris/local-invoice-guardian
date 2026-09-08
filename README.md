# Local Invoice Guardian（发票管家）

Windows 本地发票查重与费用分类工具。读取指定文件夹中的 PDF、JPG、PNG 等票据，按票面内容识别发票号、金额、日期与销售方，并与“已使用发票库”比较。

> 当前是面向 Windows 技术用户和内部试用的轻量版本，不是税务申报软件。所有结论均需财务复核。

## 功能

- 内容级查重：文件内容、发票代码/号码、金额、销方与日期多层比对
- 图片与扫描 PDF：可选智谱视觉 OCR
- 两级费用分类：票面命中二级关键词后归入一级科目
- 分类维护：可新增、改名、删除分类并编辑关键词
- 人工复核：单张改类、标记已使用、导出 CSV、复制归档

默认分类采用财务提供的一级/二级口径；自定义分类保存在本机 `config.json`。真实配置与台账不会提交到 Git。

## 普通用户安装

1. 安装 [Python 3](https://www.python.org/downloads/windows/)，安装时勾选 `Add Python to PATH`。
2. 从 GitHub Release 下载并解压源码。
3. 双击 `安装并启动.bat`。第一次会安装运行依赖，以后双击 `启动发票管家.bat` 即可。

程序只监听本机 `127.0.0.1`，默认地址为 `http://127.0.0.1:8765`。

## 开发者启动

```powershell
python -m pip install -r requirements.txt
python app.py
```

## 配置智谱 API Key

文本型 PDF 无需 API Key。JPG、PNG 和没有文本层的扫描 PDF 需要智谱视觉模型 OCR。

### 1. 获取 Key

1. 打开[智谱 API Key 管理页](https://open.bigmodel.cn/apikey/platform)并登录。
2. 点击右上角“新建 API Key”。
3. 名称可填写“本地发票管家”，确认创建。
4. 点击新记录旁的复制按钮，保存完整 API Key。

### 2. Windows 配置

打开 PowerShell，把示例文字替换成自己的 Key：

```powershell
[Environment]::SetEnvironmentVariable("ZHIPUAI_API_KEY", "替换为你的API Key", "User")
```

关闭并重新启动发票管家。可用下面的命令检查是否已配置，命令只输出状态，不显示 Key：

```powershell
if ([Environment]::GetEnvironmentVariable("ZHIPUAI_API_KEY", "User")) { "已配置" } else { "未配置" }
```

程序也兼容智谱文档常用的 `ZAI_API_KEY`。智谱官方同样建议使用环境变量，不要把 Key 硬编码进代码。[官方 API 调用说明](https://docs.bigmodel.cn/cn/guide/develop/http/introduction)

### 3. 安全与费用

- 不要把 API Key 发给他人、贴进 Issue、截图或提交到 Git。
- 如果 Key 泄露，请立即到智谱平台删除并重新创建。
- 开启 AI OCR 后，图片或扫描 PDF 页面会发送到智谱接口处理；未获授权的敏感票据请关闭 OCR。
- 模型价格、免费额度和速率限制可能调整，请以[智谱模型文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4v-flash)为准。

## 验证

```powershell
python test_core.py
python app.py --port 8799 --no-browser
python smoke_test.py
```

`smoke_test.py` 使用应用当前配置；未配置目录时仍会完成基础接口检查。HTTP 成功只代表本地功能验证，不代表财务、税务或生产验收。

## 边界

- 分类是票面建议，不等于允许报销、税前扣除或进项抵扣结论。
- 当前不自动登录电子税务局，也不执行勾选、入账或申报。
- 当前不抓取国家企业信用信息公示系统；公司抬头以本地维护为主。

## 外发版仍缺什么

- 面向普通财务的一体化安装包或签名 EXE，目前仍要求先安装 Python。
- 原生文件夹选择器和应用内安全配置 API Key；当前仍需输入路径、设置环境变量。
- 离线 OCR；当前图片 OCR 依赖第三方云服务。
- 更多发票样本的回归集，以及金额、号码、购销方字段的准确率报告。
- 自动更新、崩溃日志导出和明确的问题反馈入口。
- 税务局发票状态核验；如接入，应优先采用官方授权接口并保持只读、人工确认。

## 开源

本项目使用 [MIT License](LICENSE)。欢迎通过 GitHub Issues 提交脱敏后的问题描述；请勿上传真实发票、API Key、税号或个人信息。
