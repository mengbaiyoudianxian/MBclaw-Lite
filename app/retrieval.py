import json, struct, math
from app.models import Memory
from app.phase1_db import search_fts

def cosine_similarity(a, b):
    if not a or not b or len(a)!=len(b): return 0.0
    dot=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na>0 and nb>0 else 0.0

def decode_embedding(blob):
    n=len(blob)//4
    return list(struct.unpack('<'+str(n)+'f', blob))

def hybrid_search(db, workspace_id, query, query_vec=None, top_k=5):
    memories = db.query(Memory).filter(Memory.workspace_id==workspace_id).all()
    results=[]
    for m in memories:
        score=float(m.importance_score or 0.5)
        if query_vec and m.embedding:
            try: score=cosine_similarity(query_vec,decode_embedding(m.embedding))*0.6+score*0.4
            except: pass
        if m.type=='failure': score*=1.30
        try:
            tags=json.loads(m.tags) if m.tags else []
            for t in tags:
                if t in query: score*=1.15; break
        except: pass
        results.append({'id':m.id,'type':m.type,'content':json.loads(m.content_json) if m.content_json else {},'score':round(score,4),'importance':m.importance_score,'usage':m.usage_count or 0,'_memory_obj':m})
    results.sort(key=lambda x:x['score'],reverse=True)
    return results[:top_k]

def fts5_search(workspace_id, query, top_k=5):
    rows = search_fts(query, workspace_id=workspace_id, limit=max(top_k * 3, 30))
    results = []
    for i, r in enumerate(rows):
        score = 1.0 / (i + 1)
        if r.get('content_type') == 'failure':
            score *= 1.5
        results.append({
            'id': r['id'],
            'type': r.get('content_type'),
            'content': r.get('content'),
            'snippet': r.get('snippet'),
            'score': round(score, 4),
            'workspace_id': r.get('workspace_id'),
            'role': r.get('role'),
            'created_at': r.get('created_at'),
        })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]
def fts5_search(query, workspace_id=None, limit=10):
    from app.phase1_db import search_fts
    return search_fts(query, workspace_id, limit)
