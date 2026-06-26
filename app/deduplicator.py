"""Deduplicator — 写入前过滤层, cosine去重合并, 保留history"""
import json, struct, math

class Deduplicator:
    """语义去重器: encode→embed→dedup→write 流程中的过滤门"""

    def __init__(self, threshold=0.85):
        self.threshold = threshold
        self.stats = {'checked': 0, 'merged': 0, 'new': 0}

    def find_duplicate(self, new_embedding, candidates):
        """在候选节点中找相似>threshold的重复记忆"""
        if not new_embedding or len(new_embedding) < 10:
            return None, 0.0
        best, best_score = None, 0.0
        for c in candidates:
            if not c.embedding or len(c.embedding) < 10:
                continue
            try:
                cv = self._decode(c.embedding)
                score = self._cosine(new_embedding, cv)
                if score > self.threshold and score > best_score:
                    best, best_score = c, score
            except:
                continue
        return best, best_score

    def merge(self, old_node, new_item, new_embedding, similarity):
        """合并新旧记忆, 保留history, 返回更新dict"""
        old_content = json.loads(old_node.content_json) if old_node.content_json else {}
        if isinstance(new_item, dict):
            new_content = new_item
        elif hasattr(new_item, '__dict__'):
            new_content = new_item.__dict__
        else:
            new_content = {}

        # 保留history
        history = old_content.get('history', [])
        if not history:
            history = [old_content.get('current', old_content)]
        history.append({'content': new_content, 'merged_at_similarity': round(similarity, 4)})
        history = history[-10:]  # 最多保留10条历史

        # 合并content（按layer分发）
        layer = old_node.layer if hasattr(old_node, 'layer') else old_node.type if hasattr(old_node, 'type') else 'episode'
        merged_content = self._merge_by_layer(layer, old_content.get('current', old_content), new_content)

        # 更新embedding为加权平均
        old_emb = self._decode(old_node.embedding) if old_node.embedding else None
        merged_emb = self._avg_embedding(old_emb, new_embedding)

        return {
            'content_json': json.dumps({
                'current': merged_content,
                'history': history,
                'merge_count': len(history),
            }, ensure_ascii=False),
            'importance': min(1.0, max(float(old_node.importance or 0.5), float(new_content.get('importance', 0.5))) + 0.05),
            'embedding': merged_emb,
            'tags': json.dumps(list(set(
                json.loads(old_node.tags if old_node.tags else '[]') +
                new_content.get('tags', [])
            )), ensure_ascii=False),
        }

    def _merge_by_layer(self, layer, old, new):
        """按记忆类型分发合并策略"""
        if layer == 'semantic':
            return {
                'topic': new.get('topic', old.get('topic', '')),
                'facts': list(set(old.get('facts', []) + new.get('facts', []))),
            }
        elif layer == 'procedure':
            return {
                'task': new.get('task', old.get('task', '')),
                'steps': new.get('steps', old.get('steps', [])),
                'expected_outcome': new.get('expected_outcome', old.get('expected_outcome', '')),
            }
        elif layer == 'failure':
            return {
                'task': new.get('task', old.get('task', '')),
                'cause': new.get('cause', old.get('cause', '')),
                'lesson': new.get('lesson', old.get('lesson', '')),
            }
        else:  # episode or default
            return {
                'goal': new.get('goal', old.get('goal', '')),
                'decision': new.get('decision', old.get('decision', '')),
                'result': new.get('result', old.get('result', '')),
            }

    def _decode(self, blob):
        n = len(blob) // 4
        return list(struct.unpack('<' + str(n) + 'f', blob))

    def _cosine(self, a, b):
        dot = sum(x*y for x,y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a))
        nb = math.sqrt(sum(y*y for y in b))
        return dot/(na*nb) if na>0 and nb>0 else 0.0

    def _avg_embedding(self, emb1, emb2):
        if not emb1: return self._encode(emb2)
        if not emb2: return self._encode(emb1)
        avg = [(x+y)/2 for x,y in zip(emb1, emb2)]
        return self._encode(avg)

    def _encode(self, vec):
        return struct.pack('<' + str(len(vec)) + 'f', *vec)
