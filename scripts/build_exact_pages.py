#!/usr/bin/env python3
"""Lossless PNG page EPUB, verified pixel-for-pixel against fresh PDF rendering.
Exactness is defined at the recorded raster resolution, not PDF vector semantics.
"""
import argparse,datetime,hashlib,html,io,json,zipfile,uuid
from pathlib import Path
import pymupdf
from PIL import Image

def pixels(page):
 images=page.get_images(full=True)
 # At least native scan density; for text-only/vector pages use 300 DPI.
 scale=300/72
 for image in images:
  for rect in page.get_image_rects(image[0]):
   if rect.width>0 and rect.height>0:
    scale=max(scale,image[2]/rect.width,image[3]/rect.height)
 pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),colorspace=pymupdf.csRGB,alpha=False)
 return pix

def build(pdf,out,title):
 pdf=Path(pdf);out=Path(out)
 if out.exists():raise FileExistsError(out)
 doc=pymupdf.open(pdf);records=[];uid='urn:uuid:'+str(uuid.uuid4());esc=html.escape
 def xhtml(label,body):return f'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN" xml:lang="zh-CN"><head><title>{esc(label)}</title><style>html,body{{margin:0;padding:0}}img{{display:block;width:100%;height:auto}}p{{text-align:center}}</style></head><body>{body}</body></html>'
 out.parent.mkdir(parents=True,exist_ok=True)
 tmp=out.with_suffix('.partial.epub');items=['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'];spine=[]
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
  z.writestr('META-INF/container.xml','<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
  for i,page in enumerate(doc,1):
   pix=pixels(page);im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
   # Losslessly compact grayscale pages only when all channels are identical.
   r,g,b=im.split()
   if r.tobytes()==g.tobytes()==b.tobytes():im=r
   buf=io.BytesIO();im.save(buf,format='PNG',compress_level=6)
   z.writestr(f'OEBPS/images/{i}.png',buf.getvalue(),compress_type=zipfile.ZIP_STORED)
   z.writestr(f'OEBPS/p{i}.xhtml',xhtml(f'{title} · PDF {i}',f'<img src="images/{i}.png" alt="原 PDF 第{i}页"/>'))
   items.extend([f'<item id="p{i}" href="p{i}.xhtml" media-type="application/xhtml+xml"/>',f'<item id="i{i}" href="images/{i}.png" media-type="image/png"/>']);spine.append(f'<itemref idref="p{i}"/>')
   records.append({'page':i,'width':pix.width,'height':pix.height,'rgb_sha256':hashlib.sha256(pix.samples).hexdigest()})
   if i%50==0:print(f'{title}: built {i}/{len(doc)}',flush=True)
  nav='<nav epub:type="toc" id="toc"><h1>'+esc(title)+'</h1><p>原页保真版。逐页无损图像，文字不可重排。</p><ol>'+''.join(f'<li><a href="p{i}.xhtml">PDF 第 {i} 页</a></li>' for i in range(1,len(doc)+1))+'</ol></nav>'
  z.writestr('OEBPS/nav.xhtml',xhtml('原页目录',nav))
  now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  z.writestr('OEBPS/content.opf',f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">{uid}</dc:identifier><dc:title>{esc(title)}（原页保真版）</dc:title><dc:language>zh-CN</dc:language><meta property="dcterms:modified">{now}</meta></metadata><manifest>'+''.join(items)+'</manifest><spine>'+''.join(spine)+'</spine></package>')
 # Independent second pass through completed archive and source renderer.
 with zipfile.ZipFile(tmp) as z:
  if z.testzip() is not None: raise ValueError('ZIP integrity failure')
  for rec,page in zip(records,doc):
   im=Image.open(io.BytesIO(z.read(f'OEBPS/images/{rec["page"]}.png'))).convert('RGB');pix=pixels(page)
   if im.size!=(pix.width,pix.height) or im.size!=(rec['width'],rec['height']): raise ValueError(f'Page dimension mismatch: {rec}')
   if im.tobytes()!=pix.samples: raise ValueError(f'Pixel mismatch on page {rec["page"]}')
   rec['verified_against_fresh_pdf_render']=True
   if rec['page']%100==0:print(f'{title}: verified {rec["page"]}/{len(doc)}',flush=True)
 out.parent.mkdir(parents=True,exist_ok=True);tmp.replace(out)
 report={'source':str(pdf),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'epub':str(out),'source_pages':len(doc),'verified_pages':len(records),'all_pixels_equal':True,'definition':'Each EPUB PNG decoded to RGB equals a fresh PyMuPDF RGB render of the corresponding source PDF page at the per-page recorded native-scan resolution (300 DPI for image-free pages). Reader scaling is outside this check.','pages':records}
 out.with_suffix('.verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('DONE',out,round(out.stat().st_size/2**20,1),'MB',flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('pdf');a.add_argument('output');a.add_argument('--title',required=True);args=a.parse_args();build(args.pdf,args.output,args.title)
