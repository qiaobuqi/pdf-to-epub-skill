# PDF to EPUB Skill

用于 Codex / Claude 的 PDF 转 EPUB 与验收 Skill。支持扫描书影印转换、无损原页核验、封面标记、图片压缩和结构审计。

**不是通用 OCR 排版引擎。** 图片书不能调整正文字号；可重排文字需要可靠的文字提取/OCR 和校对。结构检查通过不代表文字零错误。

## 安装

```bash
git clone https://github.com/qiaobuqi/pdf-to-epub-skill.git ~/.agents/skills/pdf-to-epub
```

若目录已经存在，先备份或在其他目录克隆，不直接覆盖本地修改。Claude Code 可将该目录链接到 `~/.claude/skills/pdf-to-epub`。

```bash
cd ~/.agents/skills/pdf-to-epub
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Python 3.10+。审计器仅依赖标准库；图像转换需要 PyMuPDF、Pillow。处理均在本地进行，不上传 PDF。

## 使用

```bash
# 适合日常阅读的图片版（有损 JPEG）
python scripts/build_facsimile.py input.pdf book.epub --title '书名' --width 1600

# 按记录分辨率逐页渲染为无损 PNG，再独立重新渲染并比较所有 RGB 像素
python scripts/build_exact_pages.py input.pdf exact.epub --title '书名'

# 查看原 PDF，确认封面页后添加封面标记；输出必须是新文件
python scripts/set_cover.py exact.epub exact-with-cover.epub --page 1

# 压缩无损图片版：黑白页使用无损 1-bit PNG，其他页选较小编码
python scripts/compress_pages.py exact-with-cover.epub input.pdf compact.epub

# 全量结构和引用审计
python scripts/audit_epub.py compact.epub --output audit.json

# 可选：与已有逐页 OCR 缓存比较，标记需要人工复核的页面
python scripts/audit_epub.py text.epub --ocr ./ocr --output text-audit.json
```

封面/压缩命令仅支持本 Skill 生成的 `OEBPS/pN.xhtml`、`OEBPS/images/N.*` 结构；压缩输入图片须为 PNG。不要将它们当作任意第三方 EPUB 的编辑器。

压缩器会保留较小的原 PNG；二值页无损编码；符合像素一致条件时复用源 PDF JPEG；其余候选最大宽 1600px、JPEG 质量80。压缩后不再保证像素一致。

## 质量边界

- “原页一致”：记录分辨率下，EPUB PNG 解码 RGB 与源 PDF 新一轮渲染逐像素相同。不是 PDF 矢量对象等同，也不保证不同阅读器缩放后的显示完全相同。
- “结构通过”：本地检查 ZIP、XML、manifest/spine、图片引用、链接和锚点，不代替官方 EPUBCheck。
- “OCR 覆盖检查”：识别未匹配行，不能判断原 OCR 是否正确，也不能证明没有漏字。
- 不猜章节页码/ISBN，不全局替换合法汉字，不因窄行而删除题目选项。详见 [SKILL.md](SKILL.md)。
- 原页版可能很大；通常优先交付压缩版，保留源 PDF。源文件须由用户合法持有或获准处理。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试动态生成合成 PDF，检查页数、无损像素验证、封面、压缩及坏链接检测。仓库不包含真实书籍、私人文档或机器路径。

## 依赖许可

本仓库代码采用 MIT 许可。PyMuPDF 的分发/使用有其独立许可条件，请查阅安装版本的许可文件；本仓库许可不覆盖第三方依赖。
