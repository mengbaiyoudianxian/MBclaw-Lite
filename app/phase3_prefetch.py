"""Phase 3: 预调用 — 异步预检索+缓存"""
import time, threading

class PrefetchCache:
    """预调用缓存: 后台异步预检索，供下轮对话使用"""

    def __init__(self, db_session_factory):
        self.cache = {}
        self.lock = threading.Lock()
        self.db_factory = db_session_factory

    def prefetch(self, workspace_id, query_hint):
        """根据上下文提示异步预检索"""
        def _fetch():
            try:
                db = self.db_factory()
                from app.memory import search_phase1
                results = search_phase1(db, workspace_id, query_hint, top_k=10)
                with self.lock:
                    self.cache[workspace_id] = {
                        'results': results,
                        'timestamp': time.time(),
                        'query': query_hint,
                    }
                db.close()
            except Exception:
                pass

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

    def get_cached(self, workspace_id, max_age=60):
        """获取缓存结果（max_age秒内有效）"""
        with self.lock:
            entry = self.cache.get(workspace_id)
            if entry and time.time() - entry['timestamp'] < max_age:
                return entry['results']
        return None

    def clear(self, workspace_id=None):
        with self.lock:
            if workspace_id:
                self.cache.pop(workspace_id, None)
            else:
                self.cache.clear()
