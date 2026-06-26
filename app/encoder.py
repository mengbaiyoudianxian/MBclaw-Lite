import json, os

class EncodeResult:
    def __init__(self, episodes=None, semantics=None, procedures=None, failures=None):
        self.episodes = episodes or []; self.semantics = semantics or []
        self.procedures = procedures or []; self.failures = failures or []
    @property
    def total_count(self):
        return len(self.episodes)+len(self.semantics)+len(self.procedures)+len(self.failures)

class MemoryEncoder:
    def __init__(self, llm_client): self.llm = llm_client
    def encode(self, messages, workspace_id=1):
        text = '\n'.join(['['+m.get('role','user')+']: '+str(m.get('content',''))[:500] for m in messages[-40:]])
        prompt = [{'role':'user','content':'你是记忆编码器.提取4种记忆JSON: episodes/semantics/procedures/failures.每种最多3条.只输出JSON.\n\n'+text}]
        try:
            raw = self._call_llm(prompt); s=raw.find('{'); e=raw.rfind('}')+1
            if s>=0 and e>s: raw=raw[s:e]
            data=json.loads(raw)
            return EncodeResult(episodes=data.get('episodes',[])[:3],semantics=data.get('semantics',[])[:3],procedures=data.get('procedures',[])[:2],failures=data.get('failures',[])[:2])
        except: return EncodeResult()
    def _call_llm(self, messages):
        import httpx
        r=httpx.post(os.getenv('MBCLAW_LLM_BASE_URL','https://api.openai.com/v1').rstrip('/')+'/chat/completions',
            headers={'Authorization':'Bearer '+os.getenv('MBCLAW_LLM_API_KEY',''),'Content-Type':'application/json'},
            json={'model':os.getenv('MBCLAW_LLM_MODEL','gpt-4o-mini'),'messages':messages,'temperature':0.2,'max_tokens':2048},timeout=60)
        if r.status_code==200: return r.json()['choices'][0]['message']['content']
        return '{}'

def initial_importance(mem_type):
    return {'failure':0.85,'procedure':0.70,'semantic':0.50,'episode':0.30}.get(mem_type,0.50)

def adjust_importance(current, event):
    deltas={'recalled':0.05,'recalled_and_helped':0.15,'not_used_30d':-0.10,'not_used_90d':-0.30,'contradicted':-0.40}
    return max(0.05, min(1.0, current+deltas.get(event,0.0)))

def l1_judge(content):
    """Quick local judge: returns (layer, importance) based on keyword heuristics.
    layer: 'episode'|'semantic'|'procedure'|'failure'
    importance: 0.0-1.0 score"""
    c = str(content).lower()
    if any(w in c for w in ['error','fail','crash','bug','wrong','mistake','incorrect']):
        return ('failure', 0.85)
    if any(w in c for w in ['how to','step','procedure','workflow','process','run','execute']):
        return ('procedure', 0.70)
    if any(w in c for w in ['i learned','i remember','yesterday','last week','earlier','today','just now']):
        return ('episode', 0.30)
    return ('semantic', 0.50)# L1 规则引擎
L1_RULES = {
    'failure': ['失败','报错','回滚','exception','error','traceback',' refused','denied','崩溃','超时','timeout','429','500','Permission denied'],
    'decision': ['决定','选择','改为','最终方案','确认使用','采用'],
    'semantic': ['记住','注意','规则','原则','文档说','规范','标准'],
    'episode': ['上次','之前','回忆'],
}
def l1_judge(content):
    content_lower = content.lower()
    for layer, keywords in L1_RULES.items():
        for kw in keywords:
            if kw in content_lower:
                if layer == 'failure': return layer, 0.90
                elif layer == 'decision': return layer, 0.75
                elif layer == 'semantic': return layer, 0.60
                else: return layer, 0.40
    return None, 0.0
