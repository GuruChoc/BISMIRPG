import json,csv,os
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors

EXP='/mnt/data/mapleexport(6).txt'
STATUS='/mnt/data/bis_v191_unzip/lock_status.txt'
CSV='/mnt/data/bis_v191_unzip/import_review_easyocr_v191.csv'
OUT='/mnt/data/MapleStory_BIS_Report_20260818_v191_FIXED.pdf'
TXT='/mnt/data/MapleStory_BIS_Lock_Unlock_20260818_v191_FIXED.txt'

exp=json.load(open(EXP,encoding='utf-8'))
status={}
with open(STATUS,encoding='utf-8') as f:
    for line in f:
        if line.startswith(('locked|','unlocked|')):
            st,slot,id_,name,source,fn,subs=line.rstrip('\n').split('|',6)
            status[int(id_)]={'locked':st=='locked','slot':slot,'name':name,'source':source,'filename':fn,'substats':subs.split('; ') if subs else []}
meta={}
with open(CSV,newline='',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f): meta[r['filename']]=r
items={}
for slot,arr in exp['comparisonItemsBySlot'].items():
    for it in arr: items[it['id']]={**it,'slot':slot}
for slot,it in exp['equippedItemsBySlot'].items(): items[it['id']]={**it,'slot':slot}

slots=['hat','top','bottom','gloves','cape','belt','shoulder','shoes','ring','ring2','necklace','eye','face','earring']
slot_labels={'hat':'Hat','top':'Top','bottom':'Bottom','gloves':'Gloves','cape':'Cape','belt':'Belt','shoulder':'Shoulder','shoes':'Shoes','ring':'Ring','ring2':'Ring 2','necklace':'Necklace','eye':'Eye','face':'Face','earring':'Earring'}

names=exp['equipmentPresetNames']; presets=exp['equipmentPresets']

# SAFETY: OCR Equipped screenshots are authoritative for the actual Basic gear.
# The optimiser can preserve stale Basic slot IDs after a re-import, so do not allow
# an actually-equipped item to become an UNLOCK action.
equipped_by_slot={d['slot']:i for i,d in status.items() if d['source']=='equipped'}
missing_equipped=[s for s in slots if s not in equipped_by_slot]
if missing_equipped:
    raise RuntimeError('Missing Equipped OCR rows for: '+', '.join(missing_equipped))
true_basic={s:equipped_by_slot[s] for s in slots}

# Validate and record any optimiser Basic mismatch. We keep the optimiser presets
# untouched for non-Basic content, but Basic itself and inherited blank slots use
# the actual Equipped screenshots.
export_basic=presets[0]
basic_mismatches=[]
for s in slots:
    if export_basic.get(s) != true_basic[s]:
        basic_mismatches.append((s, export_basic.get(s), true_basic[s]))

effective=[]
for idx,p in enumerate(presets):
    if idx==0:
        effective.append(dict(true_basic))
    else:
        effective.append({s:p.get(s,true_basic[s]) for s in slots})
used=set(i for p in effective for i in p.values() if i)
# Absolute safety: every OCR Equipped physical item is always kept.
used.update(true_basic.values())
basic=true_basic

def find(slot,name,pred=None,all_=False):
    arr=[it for it in exp['comparisonItemsBySlot'][slot] if it['name']==name]
    if pred: arr=[it for it in arr if pred(it)]
    if all_: return [it['id'] for it in arr]
    if not arr: return None
    return arr[0]['id']

# Ring, Ring 2, Face and Necklace receive no special scarcity protection.
# Party Quest items are kept by the same rules as all other equipment: preset use, spare pool selection, or 4-substat rule.
pools={s:{'boss':[],'normal':[],'evasion':[],'accuracy':[]} for s in slots}
pools['hat']['normal']=[find('hat','23490')]
pools['top']['boss']=[find('top','23420'),find('top','23375 h 70857'),find('top','23140')]
pools['bottom']['boss']=[find('bottom','18135',lambda x:x['id']!=4220),find('bottom','23395'),find('bottom','20866')]; pools['bottom']['normal']=[find('bottom','23962')]
pools['gloves']['boss']=[find('gloves','20614 eh 19 64499')]; pools['gloves']['accuracy']=[find('gloves','20277 h 65982')]
pools['cape']['boss']=[find('cape','23425 m 27.2'),find('cape','26785'),find('cape','24040')]
pools['belt']['boss']=[find('belt','16432 h 55776'),find('belt','18700')]
pools['shoulder']['boss']=[find('shoulder','22485 h 69142')]; pools['shoulder']['normal']=[find('shoulder','26150 h 76875')]
pools['shoes']['boss']=[find('shoes','16094')]
pools['ring']['boss']=[find('ring','19344',lambda x:any(s['type']=='boss-damage' and s['value']==17.1 for s in x['stats'])),find('ring','18756'),find('ring','18924'),find('ring','17448',lambda x:any(s['type']=='boss-damage' for s in x['stats'])),find('ring','18090')]
pools['ring']['normal']=[find('ring','18174'),find('ring','19158 h 92949'),find('ring','16902',lambda x:any(s['type']=='normal-damage' for s in x['stats'])),find('ring','16818',lambda x:any(s['type']=='normal-damage' for s in x['stats'])),find('ring','18906')]
pools['ring']['evasion']=[find('ring','18216 e 32'),find('ring','17574 e 32'),find('ring','17280 e 32')]+find('ring','17154 e 32',all_=True)
pools['ring']['accuracy']=[find('ring','18474 h 93651'),find('ring','17742'),find('ring','17406'),find('ring','17112',lambda x:any(s['type']=='accuracy' for s in x['stats'])),find('ring','17070',lambda x:any(s['type']=='accuracy' for s in x['stats']))]
pools['ring2']['boss']=[find('ring2','17105'),find('ring2','15325 m 33.1')]
pools['necklace']['boss']=[find('necklace','16483'),find('necklace','14877'),find('necklace','14845 e 25'),find('necklace','11565'),find('necklace','11965')]
pools['necklace']['evasion']=[find('necklace','15579 e 27'),find('necklace','15210 e 27')]; pools['necklace']['accuracy']=[find('necklace','15394')]
pools['eye']['accuracy']=[find('eye','13788')]
pools['earring']['evasion']=[find('earring','15255 e 25'),find('earring','15145 e 25')]
for s,cats in pools.items():
    for cat,ids in cats.items(): cats[cat]=[i for i in ids if i and i not in used]
poolids=set(i for cats in pools.values() for ids in cats.values() for i in ids)
four={i for i,it in items.items() if len(it.get('stats',[]))>=4 and i in status}
extra4=four-used-poolids
keep=used|poolids|four
lock=[i for i in keep if i in status and not status[i]['locked']]
unlock=[i for i,d in status.items() if d['locked'] and i not in keep and d['source']!='equipped']

def action_row(i):
    d=status[i]; m=meta.get(d['filename'],{})
    try: order=int(m.get('batch_capture_order') or 9999)
    except: order=9999
    return {'order':order,'id':i,'slot':slot_labels[d['slot']], 'name':d['name'], 'tier':m.get('tier',''), 'level':m.get('level',''), 'sub':d['substats'][0] if d['substats'] else ''}
slot_order={slot_labels[s]:n for n,s in enumerate(slots)}
# Cleanup order: group by equipment type, then preserve true screenshot capture order within each type.
lock_rows=sorted([action_row(i) for i in lock],key=lambda r:(slot_order[r['slot']],r['order']))
unlock_rows=sorted([action_row(i) for i in unlock],key=lambda r:(slot_order[r['slot']],r['order']))

with open(TXT,'w',encoding='utf-8') as f:
    f.write('MapleStory Idle RPG - BIS Lock / Unlock Actions\n')
    f.write('OCR v191 - grouped by item type, then screenshot capture order\n')
    if basic_mismatches:
        f.write('SAFETY: Basic preset corrected from OCR Equipped screenshots for: '+', '.join(slot_labels[s] for s,_,_ in basic_mismatches)+'\n')
    f.write('\n')
    for title,rows in [('LOCK',lock_rows),('UNLOCK',unlock_rows)]:
        f.write(title+'\n')
        for r in rows:
            f.write(f"{r['order']:>3}  {r['slot']:<9} {r['name']:<22} {r['tier']} Lv.{r['level']:<3}  {r['sub']}\n")
        f.write('\n')
    if extra4:
        f.write('4-SUBSTAT ALWAYS-KEEP EXTRAS\n')
        for i in sorted(extra4): f.write(f"{slot_labels[items[i]['slot']]}  {items[i]['name']}\n")

# ---------- PDF helpers ----------
W,H=landscape(A3)
c=canvas.Canvas(OUT,pagesize=(W,H))
margin=28

def fit_text(text,maxw,font='Helvetica',size=7.0,minsize=5.2):
    s=size
    while s>minsize and stringWidth(str(text),font,s)>maxw-5: s-=0.2
    return s

def wrap_words(text,maxw,font='Helvetica',size=7.0,maxlines=2):
    words=str(text).split(); lines=[]; cur=''
    for w in words:
        test=(cur+' '+w).strip()
        if stringWidth(test,font,size)<=maxw-4: cur=test
        else:
            if cur: lines.append(cur)
            cur=w
            if len(lines)>=maxlines-1: break
    if cur and len(lines)<maxlines: lines.append(cur)
    return lines[:maxlines]

def draw_cell(x,y,w,h,text,fill=None,bold=False,fs=7.0,align='left'):
    if fill is not None:
        c.setFillColor(fill); c.rect(x,y,w,h,stroke=0,fill=1); c.setFillColor(colors.black)
    c.setLineWidth(0.55); c.rect(x,y,w,h,stroke=1,fill=0)
    font='Helvetica-Bold' if bold else 'Helvetica'
    txt='' if text is None else str(text)
    lines=wrap_words(txt,w,font,fs,2)
    if not lines: return
    usefs=fs
    if len(lines)==1: usefs=fit_text(lines[0],w,font,fs,5.0)
    c.setFont(font,usefs)
    if len(lines)==1:
        ty=y+(h-usefs)/2+1
        tx=x+3 if align=='left' else x+w/2
        c.drawString(tx,ty,lines[0]) if align=='left' else c.drawCentredString(tx,ty,lines[0])
    else:
        linefs=min(usefs,6.3)
        c.setFont(font,linefs)
        base=y+h/2+linefs*0.15
        for j,line in enumerate(lines):
            c.drawString(x+3,base-j*(linefs+0.8),line)

c.setFont('Helvetica-Bold',15); c.drawString(margin,H-32,'Equipment Set Cross-Reference')
x0=margin; ytop=H-48
preset_w=110
other_w=(W-2*margin-preset_w)/14
col_w=[preset_w]+[other_w]*14
headers=['Preset']+[slot_labels[s] for s in slots]
row_h=22
x=x0
for j,hdr in enumerate(headers): draw_cell(x,ytop-row_h,col_w[j],row_h,hdr,fill=colors.HexColor('#d9d9d9'),bold=True,fs=7.2); x+=col_w[j]

def duplicate_parent(idx):
    if idx==0:return None
    for j in range(idx):
        if effective[idx]==effective[j]: return j
    return None

order_names=['Basic Preset','Breakthrough','Chapter Boss','Arena','Colosseum','HP','MP','World Boss','Boss Raid HTE','Boss Raid ZAKVH','GD Weapon','GD Hero','GD Enhancement','GD Experience','GD Equipment']
idx_order=[names.index(n) for n in order_names]
label_over={'Breakthrough':'Chapter Breakthrough','Boss Raid HTE':'Boss Raid HTE','Boss Raid ZAKVH':'Boss Raid ZAKVH','GD Weapon':'GD Weapon','GD Hero':'GD Hero','GD Enhancement':'GD Enhancement','GD Experience':'GD Experience','GD Equipment':'GD Equipment','Colosseum':'Colosseum'}
y=ytop-row_h
for idx in idx_order:
    y-=row_h
    pname=names[idx]; parent=duplicate_parent(idx)
    rowlabel=label_over.get(pname,pname)
    if pname=='Breakthrough' and parent is not None: rowlabel+=f" ({names[parent]})"
    elif pname=='Colosseum' and parent is not None: rowlabel+=f" ({names[parent]})"
    elif parent is not None and pname not in ('GD Experience',): rowlabel+=f" ({names[parent]})"
    vals=[]
    if idx==0:
        vals=[items[effective[idx][s]]['name'] for s in slots]
    elif parent is not None:
        if parent==0: vals=['Basic']*14
        else: vals=[names[parent]]*14
    else:
        for s in slots:
            iid=effective[idx][s]
            if iid==effective[0][s]: vals.append('Basic')
            else: vals.append(items[iid]['name'])
    x=x0; draw_cell(x,y,col_w[0],row_h,rowlabel,bold=False,fs=7.0); x+=col_w[0]
    for j,v in enumerate(vals): draw_cell(x,y,col_w[j+1],row_h,v,fs=7.0); x+=col_w[j+1]

c.setFont('Helvetica-Bold',15); c.drawString(margin,y-19,'Spare Keep Pools')
sp_top=y-25
sp_headers=['Slot','Boss Keep','Normal Keep','Evasion Keep','Accuracy Keep','Kept / Total']
sp_w=[65,310,230,230,230,W-2*margin-65-310-230-230-230]
sp_h=18
x=x0
for j,hdr in enumerate(sp_headers): draw_cell(x,sp_top-sp_h,sp_w[j],sp_h,hdr,fill=colors.HexColor('#d9d9d9'),bold=True,fs=7.3); x+=sp_w[j]
counts=Counter(d['slot'] for d in status.values())
sy=sp_top-sp_h
for s in slots:
    sy-=sp_h
    vals=[slot_labels[s]]
    for cat in ['boss','normal','evasion','accuracy']:
        labs=[items[i]['name'] for i in pools[s][cat]]
        vals.append(', '.join(labs) if labs else '-')
    kept_slot=len([i for i in keep if i in status and status[i]['slot']==s])
    vals.append(f"{kept_slot}/{counts[s]}")
    x=x0
    for j,v in enumerate(vals): draw_cell(x,sy,sp_w[j],sp_h,v,bold=(j==0),fs=6.8); x+=sp_w[j]

footer_y=sy-14
c.setFont('Helvetica',7.5)
c.drawString(margin,footer_y,f"Unique IDs: {len(status)}   Keep IDs: {len(keep & set(status))}   Lock: {len(lock_rows)}   Unlock: {len(unlock_rows)}")
if basic_mismatches:
    c.setFont('Helvetica-Bold',7.2)
    c.drawRightString(W-margin,footer_y,'Basic corrected from OCR Equipped: '+', '.join(slot_labels[s] for s,_,_ in basic_mismatches))
c.showPage()

c.setFont('Helvetica-Bold',15); c.drawString(margin,H-32,'Lock / Unlock Actions - Item Type then Screenshot Order')
c.setFont('Helvetica',8); c.drawString(margin,H-45,'Grouped by equipment type; within each type, sorted by v191 batch capture order. T/Lv and first visible substat are matched to the exact screenshot record.')
if basic_mismatches:
    c.setFont('Helvetica-Bold',8); c.drawString(margin,H-56,'Safety correction: OCR Equipped overrides stale optimiser Basic for '+', '.join(slot_labels[s] for s,_,_ in basic_mismatches)+'.')
    panel_y=H-72
else:
    panel_y=H-62

def draw_action_panel(x,y,w,title,rows):
    header_h=30
    c.setFillColor(colors.HexColor('#d9d9d9')); c.rect(x,y-header_h,w,header_h,stroke=1,fill=1); c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold',17); c.drawCentredString(x+w/2,y-header_h+8,title)
    cy=y-header_h-5
    cols=[38,62,150,72,w-38-62-150-72]
    hdr=['Order','Slot','Item','T / Lv','First visible substat']
    hh=20
    xx=x
    for j,h in enumerate(hdr): draw_cell(xx,cy-hh,cols[j],hh,h,fill=colors.HexColor('#eeeeee'),bold=True,fs=7.5); xx+=cols[j]
    cy-=hh
    rh=24
    if not rows:
        draw_cell(x,cy-rh,w,rh,'No actions required',fs=8.5); cy-=rh
    for r in rows:
        xx=x
        vals=[r['order'],r['slot'],r['name'],f"{r['tier']} Lv.{r['level']}",r['sub']]
        for j,v in enumerate(vals): draw_cell(xx,cy-rh,cols[j],rh,v,fs=7.6,bold=False); xx+=cols[j]
        cy-=rh
    return cy

panel_gap=18; panel_w=(W-2*margin-panel_gap)/2
draw_action_panel(margin,panel_y,panel_w,'LOCK',lock_rows)
draw_action_panel(margin+panel_w+panel_gap,panel_y,panel_w,'UNLOCK',unlock_rows)
if extra4:
    c.setFont('Helvetica-Bold',10); c.drawString(margin,35,'4-substat always-keep extras: '+', '.join(f"{slot_labels[items[i]['slot']]} {items[i]['name']}" for i in sorted(extra4)))
c.save()
print(OUT)
print(TXT)
print('basic mismatches',[(s,a,b) for s,a,b in basic_mismatches])
print('counts',len(status),len(keep & set(status)),len(lock_rows),len(unlock_rows),'extra4',len(extra4))
