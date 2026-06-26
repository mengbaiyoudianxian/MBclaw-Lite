"""L3Refiner — 异步只读分析, 写入辅助表, 不碰核心链路"""
import threading, json, os, time

class L3Refiner:
    """LLM驱动的长期模式提炼。只写入 memory_edges/patterns, 不写 memory_nodes"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def refine(self, nodes, workspace_id):
        """提炼跨记忆规律, 返回 {patterns, edges, insights}"""
        if not nodes:
            return None

        summaries = []
        for n in nodes:
            c = json.loads(n.content_json) if n.content_json else {}
            current = c.get('current', c)
            layer = getattr(n, 'layer', 'episode')
            summaries.append(f"[{layer}] {json.dumps(current, ensure_ascii=False)[:200]}")

        prompt = f"""你是记忆抽象引擎。分析以下记忆, 提取:

1. patterns: 跨记忆重复出现的模式(最多3条)
2. edges: 记忆间的因果关系(格式: {{from: 索引, to: 索引, relation: "causes/supports/contradicts"}})
3. insights: 长期规律或教训(最多2条)

输入记忆:
{chr(10).join(summaries[:20])}

输出JSON:
{{"patterns": [{{"pattern":"","confidence":0.X,"evidence_count":N}}],
  "edges": [{{"from_idx":0,"to_idx":1,"relation":"causes","reason":"..."}}],
  "insights": [{{"insight":"","confidence":0.X}}]}}
只输出JSON."""

        try:
            raw = self._call_llm(prompt)
            s = raw.find('{'); e = raw.rfind('}')+1
            if s >= 0 and e > s:
                return json.loads(raw[s:e])
        except Exception:
            pass
        return None

    def _call_llm(self, messages_text):
        import httpx
        base = os.getenv('MBCLAW_LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        key = os.getenv('MBCLAW_LLM_API_KEY', '')
        model = os.getenv('MBCLAW_LLM_MODEL', 'gpt-4o-mini')
        r = httpx.post(f"{base}/chat/completions",
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': [{'role': 'user', 'content': messages_text}],
                  'temperature': 0.2, 'max_tokens': 2048}, timeout=120)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
        return '{}'


# ── 异步提交(不阻塞主链路) ──

_l3_queue = []
_l3_lock = threading.Lock()
_l3_running = False

def submit_async(nodes, workspace_id, llm_client=None):
    """提交L3提炼任务到后台队列"""
    global _l3_running
    with _l3_lock:
        _l3_queue.append((nodes, workspace_id, llm_client))
        if not _l3_running:
            _l3_running = True
            t = threading.Thread(target=_worker, daemon=True)
            t.start()

def _worker():
    """后台worker: 处理队列中的L3任务"""
    import logging
    log = logging.getLogger('mbclaw.l3')
    while True:
        try:
            with _l3_lock:
                if not _l3_queue:
                    global _l3_running
                    _l3_running = False
                    return
                nodes, ws_id, llm_client = _l3_queue.pop(0)

            if not llm_client:
                from app.llm import LLMClient
                llm_client = LLMClient()

            refiner = L3Refiner(llm_client)
            result = refiner.refine(nodes, ws_id)

            if result:
                _apply_result(result, nodes, ws_id)
        except Exception as e:
            log.warning(f"L3 worker error: {e}")
        time.sleep(1)

def _apply_result(result, nodes, ws_id):
    """将L3提炼结果写入辅助表(memory_edges + system_events)"""
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        # 写入edges
        for edge in result.get('edges', []):
            try:
                from app.phase1_models import MemoryEdge
                fi = edge.get('from_idx', 0)
                ti = edge.get('to_idx', 0)
                if fi < len(nodes) and ti < len(nodes):
                    e = MemoryEdge(
                        source_id=nodes[fi].id if hasattr(nodes[fi],"id") else str(nodes[fi].get("id","")),
                        target_id=nodes[ti].id if hasattr(nodes[ti],"id") else str(nodes[ti].get("id","")),
                        relation_type=edge.get('relation', 'relates_to'),
                        weight=0.6,
                    )
                    db.add(e)
            except:
                pass

        # 写入patterns/insights到system_events
        for pat in result.get('patterns', []) + result.get('insights', []):
            try:
                from app.phase1_models import SystemEvent
                ev = SystemEvent(
                    event_type='l3_pattern',
                    details_json=json.dumps(pat, ensure_ascii=False),
                )
                db.add(ev)
            except:
                pass

        db.commit()
    finally:
        db.close()
