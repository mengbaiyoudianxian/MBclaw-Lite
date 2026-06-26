"""缺口3: 用户纠错闭环 — quality_score → 0 使错误记忆不再召回"""
import json

def correct_memory(db, node_id, user_feedback='wrong'):
    """用户纠正记忆: quality_score置0, 记录修正事件"""
    from app.phase1_models import MemoryNode, SystemEvent
    from sqlalchemy import text as _tx
    
    node = db.query(MemoryNode).filter(MemoryNode.id == str(node_id)).first()
    if not node:
        return {"error": "memory not found"}
    
    old_score = node.quality_score
    
    if user_feedback == 'wrong':
        node.quality_score = 0.0
        node.importance = max(0.01, node.importance - 0.5)
    elif user_feedback == 'correct':
        node.quality_score = min(1.0, node.quality_score + 0.2)
    elif user_feedback == 'outdated':
        node.quality_score = max(0.0, node.quality_score - 0.3)
        node.decay_factor = max(0.01, (node.decay_factor or 1.0) - 0.3)
    
    # 记录修正事件
    event = SystemEvent(
        event_type='user_feedback',
        related_node_id=str(node_id),
        details_json=json.dumps({
            'feedback': user_feedback,
            'old_quality': old_score,
            'new_quality': node.quality_score,
        })
    )
    db.add(event)
    db.commit()
    
    return {
        "node_id": str(node_id),
        "action": user_feedback,
        "quality_score": node.quality_score,
        "importance": node.importance,
    }

def filter_low_quality(memories, min_quality=0.1):
    """过滤低质量记忆(quality_score < min_quality)"""
    return [m for m in memories if getattr(m, 'quality_score', 1.0) >= min_quality]

def get_correction_history(db, limit=20):
    """获取纠错历史"""
    from app.phase1_models import SystemEvent
    events = db.query(SystemEvent).filter(
        SystemEvent.event_type == 'user_feedback'
    ).order_by(SystemEvent.created_at.desc()).limit(limit).all()
    return [{
        'id': e.id, 'node_id': e.related_node_id,
        'details': json.loads(e.details_json) if e.details_json else {},
        'created_at': str(e.created_at)
    } for e in events]
