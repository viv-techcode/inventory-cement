from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root = Path.cwd()
source = root / 'docs' / 'PROJECT_EXPLAINED.md'
out = root / 'docs' / 'PROJECT_EXPLAINED.docx'
text = source.read_text(encoding='utf-8')
doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(.68); sec.bottom_margin = Inches(.68)
sec.left_margin = Inches(.72); sec.right_margin = Inches(.72)
styles = doc.styles
normal = styles['Normal']; normal.font.name='Arial'; normal.font.size=Pt(10.5); normal.font.color.rgb=RGBColor(35,45,58)
normal.paragraph_format.space_after=Pt(5); normal.paragraph_format.line_spacing=1.08
for nm, size, color in [('Title',26,'16324F'),('Subtitle',13,'49647E'),('Heading 1',18,'16324F'),('Heading 2',14,'1D527A'),('Heading 3',11.5,'28708A')]:
    s=styles[nm]; s.font.name='Arial'; s.font.size=Pt(size); s.font.bold=nm!='Subtitle'; s.font.color.rgb=RGBColor.from_string(color)
    s.paragraph_format.space_before=Pt(13 if nm.startswith('Heading') else 0); s.paragraph_format.space_after=Pt(5)
# Footer page field
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=footer.add_run('SiteStock Project Explained  •  '); r.font.name='Arial'; r.font.size=Pt(8); r.font.color.rgb=RGBColor(100,112,125)
fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)

def shade(cell, fill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=tcPr.find(qn('w:shd'))
    if shd is None: shd=OxmlElement('w:shd'); tcPr.append(shd)
    shd.set(qn('w:fill'),fill)
def cell_margins(cell, top=65, start=75, bottom=65, end=75):
    tc=cell._tc; tcPr=tc.get_or_add_tcPr(); mar=tcPr.first_child_found_in('w:tcMar')
    if mar is None: mar=OxmlElement('w:tcMar'); tcPr.append(mar)
    for k,v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        el=mar.find(qn('w:'+k))
        if el is None: el=OxmlElement('w:'+k); mar.append(el)
        el.set(qn('w:w'),str(v)); el.set(qn('w:type'),'dxa')
def set_repeat(row):
    el=OxmlElement('w:tblHeader'); el.set(qn('w:val'),'true'); row._tr.get_or_add_trPr().append(el)
def inline(p, s, size=None, color=None):
    # lightweight Markdown bold, inline code, and links
    pattern=re.compile(r'(\*\*.*?\*\*|`[^`]+`|\[[^\]]+\]\(https?://[^)]+\))')
    pos=0
    for m in pattern.finditer(s):
        if m.start()>pos: p.add_run(s[pos:m.start()])
        tok=m.group(0)
        if tok.startswith('**'):
            rr=p.add_run(tok[2:-2]); rr.bold=True
        elif tok.startswith('`'):
            rr=p.add_run(tok[1:-1]); rr.font.name='Consolas'; rr.font.size=Pt(size or 9)
            rr.font.color.rgb=RGBColor(35,83,105)
        else:
            mm=re.match(r'\[([^\]]+)\]\(([^)]+)\)',tok); rr=p.add_run(mm.group(1)+' ('+mm.group(2)+')'); rr.font.color.rgb=RGBColor(30,91,139)
        if size:
            rr.font.size=Pt(size)
        if color: rr.font.color.rgb=RGBColor.from_string(color)
        pos=m.end()
    if pos<len(s):
        rr=p.add_run(s[pos:])
        if size: rr.font.size=Pt(size)
        if color: rr.font.color.rgb=RGBColor.from_string(color)
def cell_text(cell, s, header=False, ncols=1):
    cell.text=''; p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(0); p.paragraph_format.line_spacing=1.0
    inline(p,s,size=8.3 if ncols>=5 else 8.8 if ncols>=4 else 9.2)
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; cell_margins(cell)
    for rr in p.runs:
        rr.font.name='Arial'
        if header: rr.font.bold=True; rr.font.color.rgb=RGBColor(255,255,255)
def add_table(rawrows):
    if not rawrows:return
    n=len(rawrows[0]); t=doc.add_table(rows=len(rawrows), cols=n)
    t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=True; t.style='Table Grid'
    for ri,row in enumerate(rawrows):
        for ci,val in enumerate(row):
            cell=t.cell(ri,ci); cell_text(cell,val,ri==0,n)
            if ri==0: shade(cell,'16324F')
            elif ri%2==0: shade(cell,'F1F5F8')
        if ri==0:set_repeat(t.rows[ri])
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
def add_callout(s):
    t=doc.add_table(rows=1,cols=1); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    c=t.cell(0,0); c.text=''; shade(c,'EAF2F8'); cell_margins(c,100,130,100,130)
    p=c.paragraphs[0]; p.paragraph_format.space_after=Pt(0); inline(p,s, size=9.5)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)

# Title page
p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(110); p.add_run('SiteStock Project Explained')
p=doc.add_paragraph(style='Subtitle'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run('A beginner guide and viva coach')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(20); p.add_run('Construction Materials Inventory Management  •  Dehradun / North India')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(80); p.add_run('Prepared from the project files and saved evaluation results\n3 November 2026')
doc.add_page_break()
# static TOC
h=doc.add_paragraph('Table of contents',style='Heading 1')
for line in ['Part 0  How to use this guide','Part 1  The big picture','Part 2  Basic ideas','Part 3  The dataset','Part 4  The database','Part 5  Machine learning and forecasting','Part 6  Inventory rules and risk','Part 7  Policy simulation','Part 8  How the software is built','Part 9  How to run on Windows','Part 10  Decisions and reasons','Part 11  Honest limits and future work','Part 12  Viva preparation','Part 13  Glossary and file map','Appendix A  Source check']:
    p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.15); p.paragraph_format.space_after=Pt(4); p.add_run(line)
doc.add_page_break()

lines=text.splitlines(); i=0; in_fence=False; fence=[]
while i<len(lines):
    line=lines[i]
    if line.startswith('```'):
        if not in_fence:
            in_fence=True; fence=[]
        else:
            in_fence=False
            joined='\n'.join(fence)
            if joined.startswith('flowchart'):
                labels=re.findall(r'\w+\[([^\]]+)\]',joined)
                if labels:
                    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    r=p.add_run('  →  '.join(labels)); r.bold=True; r.font.color.rgb=RGBColor(30,83,112); r.font.size=Pt(10)
            elif joined.startswith('erDiagram'):
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.15)
                r=p.add_run('Database links: sites and materials connect to stock movements and history; imports connect to historical rows and rejected rows; suppliers connect to purchase orders and lines; purchase lines connect to receipts; customers and materials connect to sales.'); r.font.size=Pt(9.5)
            else:
                for code in fence:
                    p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.18); p.paragraph_format.space_after=Pt(0)
                    r=p.add_run(code); r.font.name='Consolas'; r.font.size=Pt(8.5); r.font.color.rgb=RGBColor(48,65,78)
            fence=[]
        i+=1; continue
    if in_fence:
        fence.append(line); i+=1; continue
    if line.startswith('|') and i+1<len(lines) and re.match(r'^\|?\s*:?-{3,}',lines[i+1]):
        rows=[]
        while i<len(lines) and lines[i].startswith('|'):
            vals=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-{3,}:?',v or '-') for v in vals): rows.append(vals)
            i+=1
        if rows:
            width=max(len(r) for r in rows)
            rows=[r+['']*(width-len(r)) for r in rows]
            add_table(rows)
        continue
    if line.startswith('# '):
        i+=1; continue
    if line.startswith('## '):
        p=doc.add_paragraph(line[3:],style='Heading 1')
    elif line.startswith('### '):
        p=doc.add_paragraph(line[4:],style='Heading 2')
    elif line.startswith('#### '):
        p=doc.add_paragraph(line[5:],style='Heading 3')
    elif line.startswith('> '):
        bits=[]
        while i<len(lines) and lines[i].startswith('> '):
            bits.append(lines[i][2:].strip()); i+=1
        add_callout(' '.join(bits)); continue
    elif re.match(r'^\d+\. ',line):
        p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.20); p.paragraph_format.first_line_indent=Inches(-.20); inline(p,line)
    elif line.startswith('- '):
        p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.20); p.paragraph_format.first_line_indent=Inches(-.14); p.add_run('• '); inline(p,line[2:])
    elif line.strip():
        p=doc.add_paragraph(); inline(p,line)
    i+=1

# Set widow control and document metadata
for p in doc.paragraphs:
    pPr=p._p.get_or_add_pPr(); wc=OxmlElement('w:widowControl'); pPr.append(wc)
doc.core_properties.title='SiteStock Project Explained'
doc.core_properties.subject='Beginner project guide and viva preparation'
doc.core_properties.author='SiteStock Project'
doc.save(out)
print(f'Created {out} ({out.stat().st_size} bytes)')
