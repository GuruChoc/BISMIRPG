import json,csv,os
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors

EXP='/mnt/data/mapleexport(6).txt'
STATUS='/mnt/data/bis_v191_unzip/lock_status.txt'
CSV='/mnt/data/bis_v191_unzip/import_review_easyocr_v191.csv'
OUT='/mnt/data/MapleStory_BIS_Report_20260818_v191_CONSERVATIVE.pdf'
TXT='/mnt/data/MapleStory_BIS_Lock_Unlock_20260818_v191_CONSERVATIVE.txt'

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
used.update(true_basic.values())
basic=true_basic

# Spare keep pools are ALWAYS recalculated from the current export inventory.
# No carry-forward IDs or names from a previous report are allowed.
# Allocation is unique and left-to-right: Boss -> Normal -> Evasion -> Accuracy.
# Items already used by a preset/Basic are excluded before pool ranking.
# Ring/Ring 2/Face/Eye/Necklace keep up to Top 5 per category; all other slots Top 3.
SPECIAL_TOP5={'ring','ring2','face','eye','necklace'}
BASE=exp.get('stats',{})
BASE_CRIT=float(BASE.get('critRate',0) or 0)

NORM={
    'crit-rate':16.0,'crit-damage':17.0,'boss-damage':17.0,'normal-damage':18.0,
    'damage':22.0,'max-damage-ratio':27.0,'min-damage-ratio':27.0,
    'defense-penetration':14.0,'skill-damage':20.0,'basic-attack-damage':20.0,
    'skill-level-4':17.0,'skill-level-3':26.0,'skill-level-2':26.0,'skill-level-1':26.0,
    'attack':9000.0,'main-stat':1400.0,
}
crit_need=max(0.0,100.0-BASE_CRIT)
crit_weight=1.30 if crit_need>0.5 else 0.08
WEIGHTS={
    'boss':{
        'boss-damage':1.35,'crit-rate':crit_weight,'crit-damage':1.20,
        'skill-level-4':1.18,'defense-penetration':1.00,'damage':0.95,
        'max-damage-ratio':0.92,'min-damage-ratio':0.92,'skill-damage':0.92,
        'basic-attack-damage':0.70,'skill-level-3':0.68,'skill-level-2':0.50,
        'skill-level-1':0.42,'attack':0.72,'main-stat':0.45,'normal-damage':0.04,
    },
    'normal':{
        'normal-damage':1.35,'crit-rate':crit_weight,'crit-damage':1.20,
        'skill-level-4':1.18,'damage':0.95,'max-damage-ratio':0.92,
        'min-damage-ratio':0.92,'skill-damage':0.92,'basic-attack-damage':0.82,
        'skill-level-3':0.68,'skill-level-2':0.50,'skill-level-1':0.42,
        'attack':0.72,'main-stat':0.45,'boss-damage':0.04,'defense-penetration':0.25,
    },
}

def stat_value(it,stat_type):
    vals=[float(s.get('value',0) or 0) for s in it.get('stats',[]) if s.get('type')==stat_type]
    return max(vals) if vals else 0.0

def attack_substat(it): return stat_value(it,'attack')

def damage_priority_score(it,category):
    score=0.0
    for st,w in WEIGHTS[category].items():
        v=stat_value(it,st)
        if not v: continue
        if st=='crit-rate' and crit_need>0: v=min(v,crit_need)
        score+=w*(v/NORM.get(st,1.0))
    display_attack=float(it.get('attack',0) or 0)
    score+=min(display_attack/30000.0,1.2)*0.16
    has=lambda st: stat_value(it,st)>0
    target='boss-damage' if category=='boss' else 'normal-damage'
    if has('crit-damage') and has(target): score+=0.16
    if crit_need>0 and has('crit-rate') and has('crit-damage'): score+=0.18
    if crit_need>0 and has('crit-rate') and has(target): score+=0.14
    if has('skill-level-4') and has(target): score+=0.15
    return score

def rank_for_category(slot,category,excluded):
    candidates=[]
    for iid,it in items.items():
        if it.get('slot')!=slot or iid in excluded or iid not in status: continue
        if category in ('boss','normal'):
            primary=damage_priority_score(it,category)
            if primary<=0.12: continue
            target='boss-damage' if category=='boss' else 'normal-damage'
            candidates.append((primary,stat_value(it,target),stat_value(it,'crit-damage'),
                               stat_value(it,'crit-rate'),attack_substat(it),
                               float(it.get('attack',0) or 0),-iid,iid))
        else:
            primary=stat_value(it,category)
            if primary<=0: continue
            secondary=max(damage_priority_score(it,'normal'),damage_priority_score(it,'boss'))
            candidates.append((primary,secondary,attack_substat(it),float(it.get('attack',0) or 0),-iid,iid))
    candidates.sort(reverse=True)
    limit=5 if slot in SPECIAL_TOP5 else 3
    return [x[-1] for x in candidates[:limit]]

pools={s:{'boss':[],'normal':[],'evasion':[],'accuracy':[]} for s in slots}
allocated=set(used)
for cat in ['boss','normal','evasion','accuracy']:
    for s in slots:
        chosen=rank_for_category(s,cat,allocated)
        pools[s][cat]=chosen
        allocated.update(chosen)

poolids=set(i for cats in pools.values() for ids in cats.values() for i in ids)
four={i for i,it in items.items() if len(it.get('stats',[]))>=4 and i in status}
extra4=four-used-poolids

# CONSERVATIVE SAFETY NET: bias strongly toward KEEP.
pq_farmable_slots={'ring','ring2','face','necklace'}
DAMAGE_CLUSTER={
    'crit-rate','crit-damage','boss-damage','normal-damage','damage',
    'max-damage-ratio','min-damage-ratio','defense-penetration',
    'skill-damage','basic-attack-damage','skill-level-4','skill-level-3',
    'skill-level-2','skill-level-1','attack'
}

def meaningful_damage_lines(it):
    found=[]
    for st in DAMAGE_CLUSTER:
        v=stat_value(it,st)
        if not v: continue
        if st=='crit-rate' and crit_need<=0.5: continue
        found.append(st)
    return found

def pq_slot_quality_keep(slot,it):
    has=lambda st: stat_value(it,st)>0
    if slot=='ring':
        premium=sum(has(x) for x in ['crit-damage','skill-level-4','max-damage-ratio','min-damage-ratio','boss-damage','damage'])
        if crit_need>0.5 and has('crit-rate') and premium>=1: return True
        if premium>=2: return True
    elif slot=='necklace':
        premium=sum(has(x) for x in ['crit-damage','boss-damage','damage','attack'])
        if crit_need>0.5 and has('crit-rate') and premium>=1: return True
        if premium>=2: return True
    elif slot=='face':
        premium=sum(has(x) for x in ['crit-damage','skill-level-4','boss-damage','normal-damage','max-damage-ratio','min-damage-ratio','damage','attack'])
        if crit_need>0.5 and has('crit-rate') and premium>=1: return True
        if premium>=2: return True
    elif slot=='ring2':
        premium=sum(has(x) for x in ['skill-damage','crit-damage','skill-level-4','boss-damage','normal-damage','attack'])
        if has('skill-damage') and premium>=2: return True
        if crit_need>0.5 and has('crit-rate') and premium>=1: return True
        if premium>=2: return True
    return False

safety_quality=set()
for iid,it in items.items():
    if iid not in status: continue
    lines=meaningful_damage_lines(it)
    if len(lines)>=2 or pq_slot_quality_keep(it['slot'],it): safety_quality.add(iid)

UTILITY=['max-hp','max-mp','evasion','accuracy','defense']
best_util={}
for slot in slots:
    for st in UTILITY:
        best_util[(slot,st)]=max([stat_value(it,st) for iid,it in items.items() if it.get('slot')==slot and iid in status] or [0])
safety_utility=set()
for iid,it in items.items():
    if iid not in status: continue
    slot=it['slot']
    for st in UTILITY:
        v=stat_value(it,st); best=best_util[(slot,st)]
        if v>0 and best>0 and v>=0.95*best:
            safety_utility.add(iid); break

safety_keep=safety_quality|safety_utility
keep=used|poolids|four|safety_keep
lock=[i for i in keep if i in status and not status[i]['locked']]
unlock=[i for i,d in status.items() if d['locked'] and i not in keep and d['source']!='equipped']

def action_row(i):
    d=status[i]; m=meta.get(d['filename'],{})
    try: order=int(m.get('batch_capture_order') or 9999)
    except: order=9999
    return {'order':order,'id':i,'slot_key':d['slot'],'slot':slot_labels[d['slot']], 'name':d['name'], 'tier':m.get('tier',''), 'level':m.get('level',''), 'sub':d['substats'][0] if d['substats'] else ''}
slot_rank={s:i for i,s in enumerate(slots)}
lock_rows=sorted([action_row(i) for i in lock],key=lambda r:(slot_rank[r['slot_key']],r['order']))
unlock_rows=sorted([action_row(i) for i in unlock],key=lambda r:(slot_rank[r['slot_key']],r['order']))

with open(TXT,'w',encoding='utf-8') as f:
    f.write('MapleStory Idle RPG - BIS Lock / Unlock Actions\n')
    f.write('OCR v191 - grouped by equipment type, then screenshot capture order\n')
    f.write('Spare pools: fresh whole-item priority scoring; unique Boss -> Normal -> Evasion -> Accuracy allocation\nConservative safety: recognised multi-line damage clusters + near-best utility rolls are kept rather than unlocked\n')
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
        for j,line in enumerate(lines): c.drawString(x+3,base-j*(linefs+0.8),line)

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

c.setFont('Helvetica-Bold',15); c.drawString(margin,H-32,'Lock / Unlock Actions - Grouped by Item')
c.setFont('Helvetica',10.0); c.drawString(margin,H-46,'Equipment type first, then v191 screenshot capture order within each type. T/Lv and first visible substat match the exact screenshot record.')
c.setFont('Helvetica',8.8); c.drawString(margin,H-58,'Boss/Normal use whole-item priority scoring. Conservative safety keeps strong damage clusters and near-best utility rolls.')
if basic_mismatches:
    c.setFont('Helvetica-Bold',8.2); c.drawString(margin,H-70,'Safety correction: OCR Equipped overrides stale optimiser Basic for '+', '.join(slot_labels[s] for s,_,_ in basic_mismatches)+'.')
    panel_y=H-88
else:
    panel_y=H-76

def draw_action_panel(x,y,w,title,rows):
    header_h=30
    c.setFillColor(colors.HexColor('#d9d9d9')); c.rect(x,y-header_h,w,header_h,stroke=1,fill=1); c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold',19); c.drawCentredString(x+w/2,y-header_h+8,title)
    cy=y-header_h-5
    cols=[38,62,150,72,w-38-62-150-72]
    hdr=['Order','Slot','Item','T / Lv','First visible substat']
    hh=20
    xx=x
    for j,h in enumerate(hdr): draw_cell(xx,cy-hh,cols[j],hh,h,fill=colors.HexColor('#eeeeee'),bold=True,fs=9.4); xx+=cols[j]
    cy-=hh
    rh=33
    if not rows:
        draw_cell(x,cy-rh,w,rh,'No actions required',fs=10.0); cy-=rh
    for r in rows:
        xx=x
        vals=[r['order'],r['slot'],r['name'],f"{r['tier']} Lv.{r['level']}",r['sub']]
        for j,v in enumerate(vals): draw_cell(xx,cy-rh,cols[j],rh,v,fs=10.4,bold=False); xx+=cols[j]
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
print('counts',len(status),len(keep & set(status)),len(lock_rows),len(unlock_rows),'extra4',len(extra4),'safety_quality',len(safety_quality),'safety_utility',len(safety_utility))
