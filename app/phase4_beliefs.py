"""Phase 4: 信念层 — 从记忆模式中提炼信念/用户画像"""
import json

class BeliefExtractor:
    """从高层记忆中提取信念和用户画像"""

    def __init__(self, db_session):
        self.db = db_session

    def extract_beliefs(self, workspace_id):
        """从procedures/failures/semantics中提炼信念"""
        from app.phase1_models import MemoryNode
        nodes = self.db.query(MemoryNode).filter(
            MemoryNode.workspace_id == workspace_id,
            MemoryNode.layer.in_(['procedure', 'failure', 'semantic', 'decision'])
        ).order_by(MemoryNode.importance.desc()).limit(50).all()

        beliefs = []
        for n in nodes:
            content = json.loads(n.content_json) if n.content_json else {}
            if n.layer == 'failure':
                if content.get('lesson'):
                    beliefs.append({
                        'source': 'failure_pattern',
                        'statement': str(content.get('lesson')),
                        'evidence_count': n.usage_count or 1,
                        'source_id': n.id,
                    })
            elif n.layer == 'procedure' and n.usage_count > 2:
                beliefs.append({
                    'source': 'successful_pattern',
                    'statement': f"Effective approach: {content.get('task','')}",
                    'evidence_count': n.usage_count or 1,
                    'source_id': n.id,
                })

        return beliefs

    def update_identity(self, workspace_id):
        """从使用模式更新用户/系统画像"""
        from app.phase1_models import MemoryNode
        stats = {
            'total_failures': self.db.query(MemoryNode).filter(
                MemoryNode.workspace_id == workspace_id,
                MemoryNode.layer == 'failure').count(),
            'total_procedures': self.db.query(MemoryNode).filter(
                MemoryNode.workspace_id == workspace_id,
                MemoryNode.layer == 'procedure').count(),
            'avg_importance': self.db.query(MemoryNode).filter(
                MemoryNode.workspace_id == workspace_id).with_entities(
                    MemoryNode.importance).all(),
        }
        return stats
