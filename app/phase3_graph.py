"""Phase 3: 记忆图谱边 — 支持图传播检索"""
import json

class MemoryGraph:
    """记忆图谱: 管理 memory_edges, 支持图传播"""

    def __init__(self, db_session):
        self.db = db_session

    def add_edge(self, source_id, target_id, relation_type, weight=0.5):
        """添加边"""
        from app.phase1_models import MemoryEdge
        edge = MemoryEdge(
            source_id=str(source_id), target_id=str(target_id),
            relation_type=relation_type, weight=weight)
        self.db.add(edge)
        self.db.commit()
        return edge

    def get_neighbors(self, node_id, max_hops=1, relation_types=None, min_weight=0.6):
        """BFS图传播: 从node_id出发, 获取关联节点"""
        if relation_types is None:
            relation_types = ['supports', 'contradicts', 'learns_from', 'evolves_to']

        from app.phase1_models import MemoryEdge, MemoryNode
        import json

        visited = set()
        current = {str(node_id)}
        results = []

        for hop in range(max_hops):
            next_nodes = set()
            for nid in current:
                if nid in visited:
                    continue
                visited.add(nid)
                node = self.db.query(MemoryNode).filter(MemoryNode.id == nid).first()
                if node:
                    results.append({
                        'id': node.id, 'layer': node.layer,
                        'content': json.loads(node.content_json) if node.content_json else {},
                        'summary': node.summary,
                        'importance': node.importance,
                        'hop': hop,
                    })

                edges = self.db.query(MemoryEdge).filter(
                    MemoryEdge.source_id == nid,
                    MemoryEdge.relation_type.in_(relation_types),
                    MemoryEdge.weight >= min_weight,
                ).all()
                for e in edges:
                    next_nodes.add(e.target_id)

            current = next_nodes
            if len(results) >= 10:  # 限制10个节点
                break

        return results

    def find_contradictions(self, node_id):
        """找矛盾记忆"""
        return self.get_neighbors(node_id, max_hops=1,
                                  relation_types=['contradicts'], min_weight=0.3)
