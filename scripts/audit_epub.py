#!/usr/bin/env python3
"""Validate package and optionally compare cached OCR lines. No claim of OCR accuracy."""
import argparse, json, re, zipfile, posixpath
from pathlib import Path
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as E

def audit(path,ocr=None):
 errors=[]; warnings=[]; docs={}; result={'file':str(path),'errors':errors,'warnings':warnings}
 with zipfile.ZipFile(path) as z:
  names=set(z.namelist())
  if z.testzip(): errors.append('ZIP CRC failure')
  if z.infolist()[0].filename!='mimetype' or z.infolist()[0].compress_type!=0 or z.read('mimetype')!=b'application/epub+zip': errors.append('Invalid mimetype entry')
  for n in names:
   if n.endswith(('.xml','.opf','.ncx','.xhtml')):
    try: docs[n]=E.fromstring(z.read(n))
    except E.ParseError as e: errors.append(f'{n}: {e}')
  for n,root in docs.items():
   for el in root.iter():
    for attr in ['href','src']:
     v=el.get(attr)
     if not v: continue
     u=urlsplit(v)
     if u.scheme or u.netloc: continue
     target=posixpath.normpath(posixpath.join(posixpath.dirname(n),unquote(u.path))) if u.path else n
     if target not in names: errors.append(f'Broken link: {n} -> {v}')
     elif u.fragment and target in docs and not any(x.get('id')==unquote(u.fragment) for x in docs[target].iter()): errors.append(f'Broken fragment: {n} -> {v}')
  opfs=[(n,r) for n,r in docs.items() if n.endswith('.opf')]
  if len(opfs)!=1: errors.append('Expected one OPF'); return result
  opfn,opf=opfs[0]; ns={'o':'http://www.idpf.org/2007/opf','dc':'http://purl.org/dc/elements/1.1/'}
  items=opf.findall('o:manifest/o:item',ns); ids={x.get('id'):x for x in items}
  if len(ids)!=len(items): errors.append('Duplicate manifest IDs')
  spine=opf.findall('o:spine/o:itemref',ns); body=[]
  for x in spine:
   if x.get('idref') not in ids: errors.append('Unknown spine ID'); continue
   href=ids[x.get('idref')].get('href'); n=posixpath.normpath(posixpath.join(posixpath.dirname(opfn),href))
   if x.get('linear')!='no' and n in docs: body.append(''.join(docs[n].itertext()))
  text='\n'.join(body); norm=lambda s: re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]','',s)
  corpus=norm(text)
  result.update(title=opf.findtext('o:metadata/dc:title',namespaces=ns),size_mb=round(Path(path).stat().st_size/2**20,2),linear_documents=len(body),text_chars=len(corpus),image_count=sum(i.get('media-type','').startswith('image/') for i in items),spine_documents=len(spine))
  if '\ufffd' in text: warnings.append('Replacement character U+FFFD found')
  if ocr:
   pages=[]
   for f in sorted(Path(ocr).glob('pg-*.json')):
    data=json.loads(f.read_text()); lines=data.get('lines',[]); eligible=[]; missing=[]
    if data.get('error'): errors.append(f'OCR error {f.name}: {data["error"]}')
    for l in lines:
     t=norm(l['text'])
     if len(t)<14 or not .08<l.get('y',.5)<.88: continue
     eligible.append(t)
     # Character substitution can fail an exact line while retaining content: flag, never delete or auto-fix.
     if t not in corpus: missing.append(l['text'])
    pages.append({'page':int(f.stem.split('-')[-1]),'eligible_lines':len(eligible),'unmatched_lines':len(missing),'samples':missing[:3]})
   result['ocr_pages']=len(pages);result['ocr_comparison']=pages
   result['high_mismatch_pages']=[p for p in pages if p['eligible_lines']>=8 and p['unmatched_lines']/p['eligible_lines']>.5]
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('epub');p.add_argument('--ocr');p.add_argument('--output');a=p.parse_args()
 r=audit(a.epub,a.ocr);s=json.dumps(r,ensure_ascii=False,indent=2)
 if a.output: Path(a.output).write_text(s)
 else: print(s)
 raise SystemExit(bool(r['errors']))
