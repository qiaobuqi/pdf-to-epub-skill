#!/usr/bin/env python3
import io,zipfile,json,hashlib,datetime,sys
from pathlib import Path
from PIL import Image,ImageChops
import pymupdf
from xml.etree import ElementTree as E
sys.path.insert(0,str(Path(__file__).parent));from audit_epub import audit

def compress(epub,pdf,output,width=1600,quality=80):
 epub=Path(epub);output=Path(output);doc=pymupdf.open(pdf);mapping={};records=[]
 if output.exists():raise FileExistsError(output)
 output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_suffix('.partial.epub')
 with zipfile.ZipFile(epub) as src,zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as dst:
  dst.writestr('mimetype',src.read('mimetype'),compress_type=zipfile.ZIP_STORED)
  for i,page in enumerate(doc,1):
   old=f'OEBPS/images/{i}.png';data=src.read(old);im=Image.open(io.BytesIO(data));im.load();options=[(len(data),'png',data,'unchanged')]
   colors=im.getcolors(3)
   if im.mode in ('L','1') and colors and all(c in (0,255) for _,c in colors):
    bit=im.convert('1',dither=Image.Dither.NONE);buf=io.BytesIO();bit.save(buf,format='PNG',optimize=True);options.append((len(buf.getvalue()),'png',buf.getvalue(),'lossless-bilevel'))
   else:
    resized=im.copy();resized.thumbnail((width,10000),Image.Resampling.LANCZOS);buf=io.BytesIO();resized.save(buf,format='JPEG',quality=quality,optimize=True);options.append((len(buf.getvalue()),'jpg',buf.getvalue(),'jpeg-resized'))
    imgs=page.get_images(full=True)
    if len(imgs)==1:
     extracted=doc.extract_image(imgs[0][0])
     if extracted['ext']=='jpeg':
      original=Image.open(io.BytesIO(extracted['image'])).convert('RGB')
      # Reuse only if it depicts exactly the same full page after decoding.
      if original.size==im.size and ImageChops.difference(original,im.convert('RGB')).getbbox() is None:
       options.append((len(extracted['image']),'jpg',extracted['image'],'original-pdf-jpeg'))
   _,ext,data,mode=min(options,key=lambda x:x[0]);new=f'OEBPS/images/{i}.{ext}';mapping[old]=new;dst.writestr(new,data,compress_type=zipfile.ZIP_STORED)
   decoded=Image.open(io.BytesIO(data));decoded.load();records.append({'page':i,'mode':mode,'old_bytes':src.getinfo(old).file_size,'new_bytes':len(data),'dimensions':decoded.size,'sha256':hashlib.sha256(data).hexdigest()})
   if i%100==0:print(epub.stem,i,len(doc),flush=True)
  for info in src.infolist():
   if info.filename=='mimetype' or info.filename in mapping:continue
   data=src.read(info.filename)
   if info.filename.endswith(('.opf','.xhtml','.ncx')):
    s=data.decode()
    if info.filename.endswith('.opf'):
     ns='http://www.idpf.org/2007/opf';E.register_namespace('',ns);E.register_namespace('dc','http://purl.org/dc/elements/1.1/');r=E.fromstring(s)
     for el in r.iter():
      href=el.get('href')
      if href and 'OEBPS/'+href in mapping:
       new=mapping['OEBPS/'+href][6:];el.set('href',new)
       if el.tag.endswith('item'):el.set('media-type','image/jpeg' if new.endswith('.jpg') else 'image/png')
      if el.tag.endswith('title') and el.text:el.text=el.text.replace('原页保真版','压缩版')
      if el.get('property')=='dcterms:modified':el.text=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
     s=E.tostring(r,encoding='unicode')
    else:
     for old,new in mapping.items():
      if old!=new:s=s.replace(old[6:],new[6:])
     s=s.replace('原页保真版。逐页无损图像','压缩版。逐页图像')
    data=s.encode()
   dst.writestr(info,data)
 result=audit(tmp)
 if result['errors']:raise ValueError(result['errors'])
 with zipfile.ZipFile(tmp) as z:
  for rec in records:
   name=mapping[f'OEBPS/images/{rec["page"]}.png'];data=z.read(name)
   if hashlib.sha256(data).hexdigest()!=rec['sha256']:raise ValueError('image integrity')
   im=Image.open(io.BytesIO(data));im.load()
  r=E.fromstring(z.read('OEBPS/content.opf'));ns={'o':'http://www.idpf.org/2007/opf'}
  if [x.get('idref') for x in r.findall('o:spine/o:itemref',ns)]!=[f'p{i}' for i in range(1,len(doc)+1)]:raise ValueError('page order')
  if r.find('o:manifest/o:item[@properties="cover-image"]',ns) is None:raise ValueError('cover lost')
 tmp.replace(output);report={'input':str(epub),'output':str(output),'before_bytes':epub.stat().st_size,'after_bytes':output.stat().st_size,'page_count':len(records),'width_limit_for_reencoded_pages':width,'jpeg_quality':quality,'structural_errors':result['errors'],'all_images_decoded':True,'spine_order_verified':True,'cover_verified':True,'pages':records}
 output.with_suffix('.compression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('DONE',output,round(output.stat().st_size/2**20,2),flush=True)
if __name__=='__main__':compress(*sys.argv[1:4])
