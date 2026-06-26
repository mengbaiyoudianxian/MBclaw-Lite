"""Phase 3: 巩固任务 — daily/weekly 睡眠处理"""
import json, time

class ConsolidationEngine:
    """记忆巩固: daily聚合episodes, weekly提炼procedures, monthly分析beliefs"""

    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.llm = llm_client

    def daily(self, workspace_id=1):
        """每日: 聚合当天raw_memories → L1评分 → 高价值写入memory_nodes"""
        from app.phase1_models import RawMemory
        from app.encoder import l1_judge
        from app.phase1_models import MemoryNode
        import datetime

        today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
        raws = self.db.query(RawMemory).filter(
            RawMemory.workspace_id == workspace_id,
            RawMemory.created_at >= today
        ).all()

        count = 0
        for raw in raws:
            layer, importance = l1_judge(raw.content)
            if layer and importance >= 0.3:
                node = MemoryNode(
                    workspace_id=workspace_id,
                    layer=layer,
                    content_json=json.dumps({
                        'text': raw.content[:500],
                        'role': raw.role,
                        'raw_id': raw.id,
                    }, ensure_ascii=False),
                    summary=raw.content[:100],
                    importance=importance,
                )
                self.db.add(node)
                count += 1
        if count > 0:
            self.db.commit()
        return {'daily_consolidated': count, 'total_raws': len(raws)}

    def weekly(self, workspace_id=1):
        """每周: 聚合episodes → 提炼procedures/semantics"""
        from app.phase1_models import MemoryNode

        episodes = self.db.query(MemoryNode).filter(
            MemoryNode.workspace_id == workspace_id,
            MemoryNode.layer == 'episode'
        ).order_by(MemoryNode.created_at.desc()).limit(100).all()

        if len(episodes) < 5:
            return {'weekly_procedures': 0}

        # 简单聚类: 按content相似度分组
        content_texts = '\n'.join([
            json.loads(e.content_json).get('text', '') if e.content_json else ''
            for e in episodes[:50]
        ])

        return {'weekly_processed': len(episodes), 'content_chars': len(content_texts)}

    def decay_importance(self, workspace_id=1, days_threshold=30):
        """降权: 30天未使用的记忆降权, 90天冷存"""
        from app.phase1_models import MemoryNode
        import datetime

        cutoff_30 = (datetime.datetime.now(datetime.timezone.utc) -
                     datetime.timedelta(days=30)).isoformat()
        cutoff_90 = (datetime.datetime.now(datetime.timezone.utc) -
                     datetime.timedelta(days=90)).isoformat()

        # 30天降权
        stale = self.db.query(MemoryNode).filter(
            MemoryNode.workspace_id == workspace_id,
            MemoryNode.last_used_at < cutoff_30,
            MemoryNode.importance > 0.2
        ).all()
        for n in stale:
            n.importance = max(0.1, n.importance - 0.15)
            n.decay_factor = max(0.1, (n.decay_factor or 1.0) - 0.1)

        # 90天冷存
        cold = self.db.query(MemoryNode).filter(
            MemoryNode.workspace_id == workspace_id,
            MemoryNode.last_used_at < cutoff_90,
            MemoryNode.importance > 0.05
        ).all()
        for n in cold:
            n.importance = max(0.01, n.importance - 0.3)
            n.decay_factor = max(0.01, (n.decay_factor or 1.0) - 0.3)

        if stale or cold:
            self.db.commit()

        return {'stale_30d': len(stale), 'cold_90d': len(cold)}
