# Step 5B (Part 2) — Email, Manual Entry, Review UI, Commit, Router

Continuation of `step-05b-ingestion.md`. Complete Part 1 first.

---

## 5B.5 Email parsing — `app/routers/inbound_email.py`

Each restaurant gets a unique inbound address (`invoices+{short_id}@yourplatform.com`). Configure via SendGrid Inbound Parse (or Postmark/Mailgun) pointing the webhook at `POST /inbound-email`.

```python
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.ingestion import StagedIngestion
import anthropic, json

router = APIRouter(prefix='/inbound-email', tags=['ingestion'])
client = anthropic.Anthropic()

EMAIL_PROMPT = (
    'Extract invoice data from this distributor email. '
    'Return ONLY valid JSON: {"vendor_name":"str","invoice_number":"str or null",'
    '"received_date":"YYYY-MM-DD or null","total_amount":number or null,'
    '"line_items":[{"ingredient_name":"str","quantity":number,'
    '"unit":"str","unit_cost":number or null}]}. No markdown.'
)

def restaurant_from_email(db: Session, to_address: str):
    if 'invoices+' not in to_address: return None
    short_id = to_address.split('invoices+')[1].split('@')[0]
    return db.query(Restaurant).filter(Restaurant.invoice_email_id==short_id).first()

@router.post('/')
async def receive_email(request: Request, db: Session=Depends(get_db)):
    form        = await request.form()
    to_email    = form.get('to', '')
    email_text  = form.get('text','') or form.get('html','')
    restaurant  = restaurant_from_email(db, to_email)
    if not restaurant: return {'status':'ignored'}

    resp = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=1500,
        messages=[{'role':'user','content':EMAIL_PROMPT+'\n\nEMAIL:\n'+email_text[:4000]}])
    raw = resp.content[0].text.strip()
    if raw.startswith('```'): raw = '\n'.join(raw.split('\n')[1:-1])
    extracted = json.loads(raw)

    staged = StagedIngestion(
        restaurant_id     = str(restaurant.id),
        ingestion_type    = 'email',
        import_type       = 'invoice',
        raw_input         = email_text[:2000],
        extracted_data    = json.dumps(extracted),
        confidence_scores = json.dumps({'overall': 0.88}),
    )
    db.add(staged); db.commit()
    return {'status':'staged','id':str(staged.id)}
```

> When onboarding a restaurant, generate a short `invoice_email_id` (e.g. `abc123`) and show them their unique inbound address in settings.

---

## 5B.6 Quick sales entry — `frontend/src/pages/QuickSalesEntry.tsx`

```tsx
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/client';
import { format } from 'date-fns';

export function QuickSalesEntry() {
  const [date, setDate]     = useState(format(new Date(),'yyyy-MM-dd'));
  const [counts, setCounts] = useState<Record<string,string>>({});

  const { data: menuItems } = useQuery({
    queryKey:['menu-items'],
    queryFn: ()=>api.get('/menu-items/').then(r=>r.data),
  });

  const submit = useMutation({
    mutationFn: ()=>api.post('/sales/record-batch',{
      business_date: new Date(date).toISOString(),
      items: Object.entries(counts)
        .filter(([,qty])=>parseInt(qty)>0)
        .map(([menu_item_id, qty])=>({
          menu_item_id,
          quantity_sold: parseInt(qty),
          gross_revenue: parseInt(qty) *
            (menuItems?.find((m:any)=>m.id===menu_item_id)?.menu_price||0),
        })),
    }),
    onSuccess: ()=>{ setCounts({}); alert('Recorded!'); },
  });

  const byCategory = (menuItems||[]).reduce((acc:any,item:any)=>{
    const c=item.category||'Other'; acc[c]=[...(acc[c]||[]),item]; return acc;
  },{});

  return (
    <div className='p-4 max-w-lg mx-auto'>
      <h1 className='text-xl font-bold text-slate-800 mb-4'>End-of-Day Sales</h1>
      <input type='date' value={date} onChange={e=>setDate(e.target.value)}
             className='mb-4 border rounded px-3 py-2 w-full text-sm' />
      {Object.entries(byCategory).map(([cat,items]:any)=>(
        <div key={cat} className='mb-5'>
          <p className='text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2'>{cat}</p>
          {items.map((item:any)=>(
            <div key={item.id} className='flex items-center gap-3 mb-1.5'>
              <span className='flex-1 text-sm text-slate-700'>{item.name}</span>
              <span className='text-xs text-slate-400 w-12 text-right'>${item.menu_price}</span>
              <input type='number' min='0' placeholder='0' value={counts[item.id]||''}
                onChange={e=>setCounts(p=>({...p,[item.id]:e.target.value}))}
                className='w-16 text-center border rounded px-2 py-1 text-sm
                           focus:border-blue-400 focus:ring-1 focus:ring-blue-200 outline-none' />
            </div>
          ))}
        </div>
      ))}
      <button onClick={()=>submit.mutate()} disabled={submit.isPending}
        className='w-full bg-blue-600 text-white py-3 rounded-lg font-semibold
                   hover:bg-blue-700 disabled:opacity-50 mt-2'>
        {submit.isPending?'Saving...':'Record Sales & Update Inventory'}
      </button>
    </div>
  );
}
```

---

## 5B.7 Review UI — `frontend/src/pages/ReviewIngestion.tsx`

Shared across all automated methods. Confidence scores drive highlighting: green > 0.85, yellow 0.6–0.85, red < 0.6.

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../api/client';

const confColor = (s:number) =>
  s>0.85 ? 'border-green-300 bg-green-50' :
  s>0.60 ? 'border-yellow-300 bg-yellow-50' : 'border-red-300 bg-red-50';

export function ReviewIngestion({ stagedId }:{ stagedId:string }) {
  const qc = useQueryClient();
  const { data:staged } = useQuery({
    queryKey:['staged',stagedId],
    queryFn: ()=>api.get('/ingestion/staged/'+stagedId).then(r=>r.data),
  });
  const [edits, setEdits] = useState<any>(null);
  const raw  = staged ? JSON.parse(staged.extracted_data) : null;
  const data = edits || raw;

  const confirm = useMutation({
    mutationFn: ()=>api.post('/ingestion/staged/'+stagedId+'/confirm',{corrected_data:data}),
    onSuccess: ()=>{ qc.invalidateQueries(['staged']); },
  });
  const reject = useMutation({
    mutationFn: ()=>api.post('/ingestion/staged/'+stagedId+'/reject'),
    onSuccess: ()=>{ qc.invalidateQueries(['staged']); },
  });

  if (!staged||!data) return <div className='p-4 text-slate-400'>Loading...</div>;
  const isInvoice = staged.import_type==='invoice';
  const items     = isInvoice ? data.line_items : data.items;
  const itemsKey  = isInvoice ? 'line_items' : 'items';

  const updateItem = (i:number, field:string, value:any) => {
    const updated = [...items];
    updated[i] = {...updated[i],[field]:value};
    setEdits((p:any)=>({...(p||raw),[itemsKey]:updated}));
  };

  return (
    <div className='p-4 max-w-2xl mx-auto'>
      <div className='flex justify-between items-start mb-4'>
        <div>
          <h1 className='text-lg font-bold text-slate-800'>
            Review {isInvoice?'Invoice':'Inventory Count'}
          </h1>
          <p className='text-xs text-slate-400'>via {staged.ingestion_type.replace(/_/g,' ')}</p>
        </div>
      </div>

      {isInvoice && (
        <div className='grid grid-cols-2 gap-3 mb-4 p-3 bg-slate-50 rounded-lg'>
          <div>
            <label className='text-xs text-slate-500'>Vendor</label>
            <input value={data.vendor_name||''} placeholder='Vendor name'
              className='w-full border rounded px-2 py-1 text-sm mt-0.5'
              onChange={e=>setEdits((p:any)=>({...(p||raw),vendor_name:e.target.value}))} />
          </div>
          <div>
            <label className='text-xs text-slate-500'>Invoice #</label>
            <input value={data.invoice_number||''} placeholder='Optional'
              className='w-full border rounded px-2 py-1 text-sm mt-0.5'
              onChange={e=>setEdits((p:any)=>({...(p||raw),invoice_number:e.target.value}))} />
          </div>
        </div>
      )}

      <div className='space-y-2 mb-5'>
        {items?.map((item:any,i:number)=>(
          <div key={i} className={'border rounded-lg p-3 '+confColor(item.confidence||0.9)}>
            <div className='flex gap-2 items-center flex-wrap'>
              <input value={item.ingredient_name||''} placeholder='Ingredient name'
                className='flex-1 min-w-32 bg-transparent border-b border-transparent
                           focus:border-slate-300 outline-none text-sm font-medium'
                onChange={e=>updateItem(i,'ingredient_name',e.target.value)} />
              <input type='number' value={item.quantity||''} placeholder='Qty'
                className='w-16 text-center border rounded px-1 py-0.5 text-sm'
                onChange={e=>updateItem(i,'quantity',parseFloat(e.target.value))} />
              <input value={item.unit||''} placeholder='unit'
                className='w-16 text-center border rounded px-1 py-0.5 text-sm'
                onChange={e=>updateItem(i,'unit',e.target.value)} />
              {isInvoice && (
                <input type='number' step='0.01' value={item.unit_cost||''} placeholder='$/unit'
                  className='w-20 text-right border rounded px-1 py-0.5 text-sm'
                  onChange={e=>updateItem(i,'unit_cost',parseFloat(e.target.value))} />
              )}
            </div>
            {(item.confidence||1)<0.7 && (
              <p className='text-xs text-yellow-700 mt-1'>Low confidence — please verify</p>
            )}
          </div>
        ))}
      </div>

      {staged.raw_input && staged.ingestion_type==='voice' && (
        <details className='mb-4 text-xs text-slate-500'>
          <summary className='cursor-pointer hover:text-slate-700'>View transcript</summary>
          <p className='mt-1 p-2 bg-slate-50 rounded'>{staged.raw_input}</p>
        </details>
      )}

      <div className='flex gap-3'>
        <button onClick={()=>confirm.mutate()} disabled={confirm.isPending}
          className='flex-1 bg-blue-600 text-white py-2.5 rounded-lg font-semibold
                     hover:bg-blue-700 disabled:opacity-50'>
          {confirm.isPending?'Saving...':'Confirm & Save'}
        </button>
        <button onClick={()=>reject.mutate()}
          className='px-5 border border-red-200 text-red-500 py-2.5 rounded-lg hover:bg-red-50'>
          Reject
        </button>
      </div>
    </div>
  );
}
```

---

## 5B.8 Commit service — `app/services/ingestion_commit_service.py`

```python
import json
from sqlalchemy.orm import Session
from difflib import get_close_matches
from app.models.ingestion import StagedIngestion
from app.models.inventory import Ingredient, Vendor, InventoryCount
from app.services.inventory_service import process_invoice
from app.services.depletion_service import deplete_batch
from datetime import datetime, timezone
from types import SimpleNamespace

def fuzzy_match_ingredient(db: Session, restaurant_id: str, name: str) -> str | None:
    ingredients = db.query(Ingredient).filter(
        Ingredient.restaurant_id==restaurant_id).all()
    catalog = {i.name.lower(): str(i.id) for i in ingredients}
    matches = get_close_matches(name.lower(), catalog.keys(), n=1, cutoff=0.7)
    return catalog[matches[0]] if matches else None

def get_or_create_ingredient(db, restaurant_id, name, unit, cost):
    iid = fuzzy_match_ingredient(db, restaurant_id, name)
    if iid: return iid
    new_ing = Ingredient(restaurant_id=restaurant_id, name=name,
                         unit=unit or 'lb', current_cost_per_unit=cost or 0)
    db.add(new_ing); db.flush()
    return str(new_ing.id)

def commit_staged_ingestion(db: Session, staged_id: str, restaurant_id: str,
                            user_id: str, corrected_data: dict = None) -> dict:
    staged = db.get(StagedIngestion, staged_id)
    if not staged or staged.restaurant_id != restaurant_id:
        raise ValueError('Record not found')
    if staged.status != 'pending':
        raise ValueError('Record already '+staged.status)

    data   = corrected_data or json.loads(staged.extracted_data)
    result = {'type': staged.import_type, 'committed': 0}

    if staged.import_type == 'invoice':
        vendor = db.query(Vendor).filter(
            Vendor.restaurant_id==restaurant_id,
            Vendor.name==data.get('vendor_name','Unknown'),
        ).first()
        if not vendor:
            vendor = Vendor(restaurant_id=restaurant_id, name=data.get('vendor_name','Unknown'))
            db.add(vendor); db.flush()
        line_items = []
        for item in data.get('line_items', []):
            iid = get_or_create_ingredient(db, restaurant_id, item['ingredient_name'],
                                           item.get('unit'), item.get('unit_cost'))
            line_items.append(SimpleNamespace(
                ingredient_id=iid, quantity_received=item.get('quantity',0),
                unit_cost=item.get('unit_cost') or 0))
        process_invoice(db, restaurant_id, SimpleNamespace(
            vendor_id=str(vendor.id), invoice_number=data.get('invoice_number'),
            received_at=datetime.now(timezone.utc), total_amount=data.get('total_amount'),
            line_items=line_items))
        result['committed'] = len(line_items)

    elif staged.import_type == 'inventory_count':
        for item in data.get('items', []):
            iid = fuzzy_match_ingredient(db, restaurant_id, item['ingredient_name'])
            if not iid: continue
            db.add(InventoryCount(restaurant_id=restaurant_id, ingredient_id=iid,
                                  counted_at=datetime.now(timezone.utc),
                                  quantity=item.get('quantity',0)))
            ing = db.get(Ingredient, iid)
            if ing: ing.current_stock = item.get('quantity',0)
        db.commit()
        result['committed'] = len(data.get('items',[]))

    elif staged.import_type == 'sales':
        rows  = data.get('items', data.get('rows',[]))
        sales = [{'menu_item_id':r['menu_item_id'],
                  'quantity':r.get('quantity_sold',0),
                  'revenue':r.get('gross_revenue',0)}
                 for r in rows if r.get('menu_item_id')]
        if sales: deplete_batch(db, restaurant_id, sales, datetime.now(timezone.utc))
        result['committed'] = len(sales)

    staged.status       = 'confirmed'
    staged.confirmed_at = datetime.now(timezone.utc)
    staged.confirmed_by = user_id
    db.commit()
    return result
```

---

## 5B.9 API router — `app/routers/ingestion.py`

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.database import get_db
from app.routers.auth import get_current_restaurant_id, get_current_user
from app.services.csv_ingestion_service import stage_csv_import
from app.services.ocr_ingestion_service import stage_image_upload
from app.services.voice_ingestion_service import stage_voice_count
from app.services.ingestion_commit_service import commit_staged_ingestion
from app.models.ingestion import StagedIngestion
import json

router = APIRouter(prefix='/ingestion', tags=['ingestion'])

@router.post('/csv/stage')
async def stage_csv(file: UploadFile = File(...), import_type: str = Form(...),
                    mapping: str = Form(...), label: str = Form(default=''),
                    db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    content = (await file.read()).decode('utf-8')
    staged  = stage_csv_import(db,rid,import_type,content,json.loads(mapping),label=label)
    return {'staged_id':str(staged.id),'extracted_data':json.loads(staged.extracted_data)}

@router.post('/photo/stage')
async def stage_photo(file: UploadFile = File(...), extract_type: str = Form(...),
                      db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    staged = stage_image_upload(db, rid, await file.read(), extract_type)
    return {'staged_id':str(staged.id),
            'extracted_data':json.loads(staged.extracted_data),
            'confidence_scores':json.loads(staged.confidence_scores)}

@router.post('/voice/stage')
async def stage_voice(file: UploadFile = File(...), format: str = Form(default='webm'),
                      db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    staged = stage_voice_count(db, rid, await file.read(), format)
    return {'staged_id':str(staged.id),'transcript':staged.raw_input,
            'extracted_data':json.loads(staged.extracted_data)}

@router.get('/staged')
def list_staged(db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    records = db.query(StagedIngestion).filter(
        StagedIngestion.restaurant_id==rid, StagedIngestion.status=='pending',
    ).order_by(StagedIngestion.created_at.desc()).all()
    return [{'id':str(r.id),'ingestion_type':r.ingestion_type,
             'import_type':r.import_type,'created_at':str(r.created_at),
             'extracted_data':json.loads(r.extracted_data or '{}'),
             'confidence_scores':json.loads(r.confidence_scores or '{}')}
            for r in records]

@router.get('/staged/{sid}')
def get_staged(sid:str, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    r = db.get(StagedIngestion, sid)
    if not r or r.restaurant_id!=rid: raise HTTPException(404,'Not found')
    return {'id':str(r.id),'ingestion_type':r.ingestion_type,
            'import_type':r.import_type,'created_at':str(r.created_at),
            'extracted_data':r.extracted_data,'confidence_scores':r.confidence_scores}

@router.post('/staged/{sid}/confirm')
def confirm(sid:str, body:dict={}, db=Depends(get_db),
            rid=Depends(get_current_restaurant_id), user=Depends(get_current_user)):
    return commit_staged_ingestion(db,sid,rid,str(user.id),body.get('corrected_data'))

@router.post('/staged/{sid}/reject')
def reject(sid:str, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    r = db.get(StagedIngestion, sid)
    if not r or r.restaurant_id!=rid: raise HTTPException(404,'Not found')
    r.status='rejected'; db.commit()
    return {'status':'rejected'}
```

Register in `main.py`: `app.include_router(ingestion.router)` and `app.include_router(inbound_email.router)`.

> **QR code scanning** needs no extra backend — generate codes client-side (qrcode.js) deep-linking to `/inventory/count?ingredient_id=XXX`; the standard inventory count endpoint handles submission.

---

## Done when

You can: upload a CSV and see staged rows; upload a photo of an invoice and get extracted line items; record audio and get parsed counts; confirm a staged record and verify it commits to live tables via the same services as manual entry.

## Then

Update Step 5B checkbox in `CLAUDE.md`, `git commit`, move to `step-06-alerts.md`.
