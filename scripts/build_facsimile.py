#!/usr/bin/env python3
"""Lossless page coverage, image-based EPUB; does NOT produce reflowable OCR text."""
import argparse,hashlib,html,json,uuid,zipfile,datetime
from pathlib import Path
import pymupdf

def build(pdf,output,title=None,width=1600):
 pdf=Path(pdf); output=Path(output)
 if output.exists(): raise FileExistsError(f'Refusing to overwrite {output}')
 doc=pymupdf.open(pdf)
 if doc.needs_pass: raise ValueError('Encrypted PDF requires user-provided unlocked input')
 title=title or doc.metadata.get('title') or pdf.stem
 uid='urn:uuid:'+str(uuid.uuid4()); manifest=[]; spine=[]
 esc=html.escape
 def xhtml(label,body): return f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN" xml:lang="zh-CN"><head><title>{esc(label)}</title><style>body{{margin:0}}img{{max-width:100%;height:auto}}p{{text-align:center}}</style></head><body>{body}</body></html>'
 output.parent.mkdir(parents=True,exist_ok=True); tmp=output.with_name(output.name+'.partial')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
  z.writestr('META-INF/container.xml','<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
  for i,page in enumerate(doc,1):
   pix=page.get_pixmap(matrix=pymupdf.Matrix(width/page.rect.width,width/page.rect.width),alpha=False)
   z.writestr(f'OEBPS/images/{i}.jpg',pix.tobytes('jpg',jpg_quality=85))
   z.writestr(f'OEBPS/p{i}.xhtml',xhtml(f'{title} · 第{i}页',f'<p><a href="nav.xhtml">目录</a> · 第{i}页</p><img src="images/{i}.jpg" alt="原 PDF 第{i}页"/>'))
   manifest.extend([f'<item id="p{i}" href="p{i}.xhtml" media-type="application/xhtml+xml"/>',f'<item id="i{i}" href="images/{i}.jpg" media-type="image/jpeg"/>']);spine.append(f'<itemref idref="p{i}"/>')
  toc=[(label,page) for _,label,page in doc.get_toc() if 1<=page<=len(doc)] or [(f'第 {i} 页',i) for i in range(1,len(doc)+1)]
  nav='<nav epub:type="toc" id="toc"><h1>'+esc(title)+'</h1><p>影印版 EPUB：保留全部原页，文字不能重排。</p><ol>'+''.join(f'<li><a href="p{p}.xhtml">{esc(t)}</a></li>' for t,p in toc)+'</ol></nav>'
  z.writestr('OEBPS/nav.xhtml',xhtml('目录',nav));manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
  now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  z.writestr('OEBPS/content.opf',f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">{uid}</dc:identifier><dc:title>{esc(title)}</dc:title><dc:language>zh-CN</dc:language><meta property="dcterms:modified">{now}</meta></metadata><manifest>'+''.join(manifest)+'</manifest><spine>'+''.join(spine)+'</spine></package>')
 tmp.replace(output)
 report={'pdf':str(pdf),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'epub':str(output),'source_pages':len(doc),'embedded_pages':len(doc),'mode':'facsimile','render_width':width,'quality_claim':'All source pages rendered; no OCR or textual accuracy claim.'}
 output.with_suffix('.provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('output');p.add_argument('--title');p.add_argument('--width',type=int,default=1600);a=p.parse_args()
 if not 600<=a.width<=4000:p.error('width must be 600..4000')
 print(json.dumps(build(a.pdf,a.output,a.title,a.width),ensure_ascii=False,indent=2))
