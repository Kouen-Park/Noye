"""Read-only extraction and rendering of two actual native QA exports."""
import hashlib,json,pathlib
import httpx,pymupdf
root=pathlib.Path('/private/tmp/noye-phase8-20261016')
reports={}
with httpx.Client(trust_env=False,timeout=10) as client:
    for kind,name in [('short','Phase8 generated AT-201'),('complex','Phase 8 complex PDF QA')]:
        before=json.loads((root/f'native-literal-{kind}-before.json').read_text())
        after=client.get('http://127.0.0.1:62715/documents/'+before['id']).raise_for_status().json()
        path=root/'exports/literal-final'/f'{name}.pdf'
        renders=[]
        with pymupdf.open(path) as pdf:
            texts=[p.get_text() for p in pdf]
            text='\n'.join(texts)
            flat=''.join(text.split())
            for i,page in enumerate(pdf):
                png=root/f'native-literal-{kind}-page-{i+1}.png'
                page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(png)
                renders.append(str(png))
            checks={'markdown_unchanged':before['content']==after['content'],'no_toolbar':'Export PDF' not in text,'no_ligature_fi':'ﬁ' not in text}
            if kind=='short':
                checks.update({'one_page':len(pdf)==1,'literal_comment':'<!--Phase8Markdownfidelity-->' in flat,'literal_arrow':'->' in text,'measures':'12 milliseconds' in text and '37 megabytes' in text,'korean':'생성 문서 편집 검증.' in text})
            else:
                checks.update({'all_table_rows':all(f'TOKEN-{n:03}-END' in text for n in range(1,41)),'all_code_lines':all(f'END-C{n:03}' in flat for n in range(1,41)),'all_list_items':all(f'L{n:03}' in text for n in range(1,17)),'final_sentinel':'FINAL-PDF-ALL-CONTENT-20261015' in text,'korean':'끝까지 보존.' in text,'image_heading_and_caption_same_page':any('Image / 로컬 이미지' in t and 'Image caption:' in t for t in texts)})
            reports[kind]={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(pdf),'text':text,'checks':checks,'renders':renders,'visual_accepted':None,'body_sha256':hashlib.sha256(before['content'].encode()).hexdigest()}
report={'method':__doc__,'short_first_panel':'Save enabled on initial observation; changed directory to a new QA-only destination to preserve existing PDF.','complex_second_panel':'Initial AX disabled Save; next screenshot and AX enabled it without any input. Save succeeded without modifying filename or directory. Transient delay, not a confirmed persistent regression.','reports':reports}
(root/'native-literal-final-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{'pages':v['pages'],'bytes':v['bytes'],'checks':v['checks']} for k,v in reports.items()},ensure_ascii=False))
