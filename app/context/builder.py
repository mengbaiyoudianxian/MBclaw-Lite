import json
from app.memory import search_phase1

class ContextBuilder:
    def __init__(self, db): self.db = db
    def build(self, workspace_id, query='', top_k=5):
        results = search_phase1(self.db, workspace_id, query, top_k)
        has_failure = any(r.get('type')=='failure' for r in results)
        if not has_failure:
            from app.models import Memory as M
            failures = self.db.query(M).filter(
                M.workspace_id==workspace_id, M.type=='failure'
            ).order_by(M.importance_score.desc()).limit(2).all()
            for f in failures:
                results.append({
                    'id': f.id, 'type': 'failure',
                    'content': json.loads(f.content_json) if f.content_json else {},
                    'score': float(f.importance_score)*1.3,
                    'importance': f.importance_score,
                })
        order = {'failure': 0, 'procedure': 1, 'semantic': 2, 'episode': 3}
        results.sort(key=lambda r: (order.get(r.get('type',''), 4), -r.get('score', 0)))
        results = results[:top_k]
        parts = []; used_ids = []
        for r in results:
            c = r.get('content', {})
            text = ''
            t = r.get('type', '')
            if t == 'failure':
                text = '[Fail]' + str(c.get('task','')) + ':' + str(c.get('lesson',''))
            elif t == 'procedure':
                text = '[HowTo]' + str(c.get('task','')) + ':' + str(c.get('steps',[]))
            elif t == 'semantic':
                text = '[Fact]' + str(c.get('topic','')) + ':' + str(c.get('facts',[]))
            elif t == 'episode':
                text = '[Event]' + str(c.get('goal','')) + '->' + str(c.get('result',''))
            else:
                text = str(r.get('summary','')) or str(c)[:100]
            if text and len('\n'.join(parts)+'\n'+text) < 800:
                parts.append(text); used_ids.append(r.get('id'))
        return '\n'.join(parts)[:800], used_ids
