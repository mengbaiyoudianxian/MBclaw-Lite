"""Phase 4: Failure 环境指纹 + 分类 + 成本度量"""
import json, os, re

def classify_failure(error_text, context=''):
    """分类失败类型: environmental / logic / knowledge_gap"""
    text = (error_text + ' ' + context).lower()
    env_keywords = ['timeout', 'connection refused', 'network', 'dns', '429',
                    'rate limit', 'quota', '磁盘满', '内存不足', 'oom']
    logic_keywords = ['syntaxerror', 'typeerror', 'attributeerror', 'nameerror',
                      'indexerror', 'keyerror', '逻辑', '空指针', 'null pointer',
                      'assertionerror', 'valueerror']
    gap_keywords = ['deprecated', 'not found', 'no module', '不支持', 'no such',
                    'not supported', '已被移除']

    for kw in env_keywords:
        if kw in text: return 'environmental'
    for kw in logic_keywords:
        if kw in text: return 'logic'
    for kw in gap_keywords:
        if kw in text: return 'knowledge_gap'
    return 'logic'  # 默认

def capture_env_snapshot():
    """捕获当前环境指纹 (Python版本+关键依赖)"""
    import sys
    snapshot = {'python': sys.version.split()[0], 'packages': {}}
    try:
        import pkg_resources
        for pkg in ['fastapi', 'sqlalchemy', 'pydantic', 'numpy', 'httpx', 'jieba']:
            try: snapshot['packages'][pkg] = pkg_resources.get_distribution(pkg).version
            except: pass
    except: pass
    return snapshot

def estimate_cost(failure_data):
    """估算失败成本: tokens_wasted + retry_count + time"""
    cost = 0.0
    if failure_data.get('tokens_wasted', 0) > 10000: cost += 0.3
    if failure_data.get('tokens_wasted', 0) > 100000: cost += 0.3
    if failure_data.get('retry_count', 0) > 3: cost += 0.2
    if failure_data.get('time_spent_seconds', 0) > 300: cost += 0.2
    return min(1.0, cost)

def should_block(failure, current_env=None):
    """判断是否应该强拦截某个failure"""
    if failure.get('failure_type') == 'environmental':
        return False  # 环境失败不拦截
    if failure.get('importance', 0) < 0.7:
        return False
    # 环境指纹比对: 主版本号变化 → 只提醒不拦截
    if current_env and failure.get('env_snapshot'):
        old_py = failure['env_snapshot'].get('python', '')
        new_py = current_env.get('python', '')
        if old_py.split('.')[0] != new_py.split('.')[0]:
            return False  # 主版本变了，不拦截
    return True
