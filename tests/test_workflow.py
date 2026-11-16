import tempfile,sys,zipfile,json,unittest
from pathlib import Path
from xml.etree import ElementTree as E
import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_exact_pages import build
from build_facsimile import build as facsimile
from set_cover import set_cover
from compress_pages import compress
from audit_epub import audit
class Workflow(unittest.TestCase):
 def test_roundtrip_and_bad_link(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);pdf=d/'source.pdf';doc=pymupdf.open()
   for i in range(3):
    p=doc.new_page(width=240,height=320);p.insert_text((20,40),f'Page {i+1}');p.draw_rect((20,60,200,250),color=(0,.3,.7))
   doc.save(pdf);doc.close()
   raw=d/'new'/'exact.epub';build(pdf,raw,'Test')
   report=json.loads(raw.with_suffix('.verification.json').read_text())
   self.assertEqual(report['verified_pages'],3);self.assertTrue(report['all_pixels_equal'])
   covered=d/'cover.epub';set_cover(raw,covered,1)
   with zipfile.ZipFile(covered) as z:
    root=E.fromstring(z.read('OEBPS/content.opf'));self.assertEqual(root.find('{http://www.idpf.org/2007/opf}manifest/{http://www.idpf.org/2007/opf}item[@properties="cover-image"]').get('href'),'images/1.png')
   small=d/'small.epub';compress(covered,pdf,small);self.assertFalse(audit(small)['errors']);self.assertEqual(audit(small)['image_count'],3)
   basic=d/'basic.epub';facsimile(pdf,basic,'Test');self.assertFalse(audit(basic)['errors'])
   bad=d/'bad.epub'
   with zipfile.ZipFile(covered) as src,zipfile.ZipFile(bad,'w') as dst:
    for item in src.infolist():
     data=src.read(item.filename)
     if item.filename=='OEBPS/p1.xhtml':data=data.replace(b'</body>',b'<a href="missing.xhtml">bad</a><a href="p2.xhtml#missing">bad fragment</a></body>')
     dst.writestr(item,data)
   errors=audit(bad)['errors'];self.assertTrue(any('Broken link' in x for x in errors));self.assertTrue(any('Broken fragment' in x for x in errors))
if __name__=='__main__':unittest.main()
