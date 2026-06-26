"""Phase 2: L2 批量评分器 — 按会话聚合，用FTS命中率+消息特征打分"""
import json

class L2Scorer:
    """L2轻量评分器。按会话批量处理，不是每条消息触发。
    用FTS命中率+消息长度+角色权重快速打分。importance<0.3的过滤。"""

    ROLE_WEIGHTS = {
        'user': 1.0,
        'assistant': 0.8,
        'system': 0.3,
        'tool': 1.2,  # 工具调用通常重要
    }

    def __init__(self, db_session):
        self.db = db_session

    def score_batch(self, messages, workspace_id=1):
        """批量评分: 输入消息列表, 输出每条消息的(layer, importance)"""
        from app.encoder import l1_judge
        from app.phase1_db import search_fts

        results = []
        for msg in messages:
            content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
            role = msg.get('role', 'user') if isinstance(msg, dict) else 'user'

            # L1 规则引擎先判
            layer, importance = l1_judge(content)

            # L2 增强: 用FTS命中率和消息特征调整 importance
            if importance > 0:
                # FTS命中率: 消息中有多少关键词在DB中命中过
                try:
                    fts_results = search_fts(content, workspace_id, limit=3)
                    fts_bonus = min(0.15, len(fts_results) * 0.05)  # 最多+0.15
                    importance = min(1.0, importance + fts_bonus)
                except:
                    pass

                # 消息长度加权: 长消息通常更有价值
                msg_len = len(content)
                if msg_len > 500:
                    importance = min(1.0, importance + 0.05)
                elif msg_len < 20:
                    importance = max(0.0, importance - 0.10)

                # 角色加权
                rw = self.ROLE_WEIGHTS.get(role, 0.5)
                importance = importance * rw

            # 过滤低价值
            if importance < 0.3:
                layer = None
                importance = 0.0

            results.append({'layer': layer, 'importance': importance, 'role': role})

        return results

    def filter_valuable(self, messages, workspace_id=1, threshold=0.3):
        """只返回importance>=threshold的消息"""
        batch = self.score_batch(messages, workspace_id)
        return [m for m in batch if m['importance'] >= threshold]
