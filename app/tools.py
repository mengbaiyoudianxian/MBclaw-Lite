"""Tool Registry — complete tool system with L1/L2/L3 display and execution.

Derived from tool_service.py + Android ToolRegistry.
Supports: file ops, shell, memory, web, browser, media, device, classification.
"""

import json, os, subprocess

from app.models import Tool




# ═══════════════════════════════════════════════════════════════
# built-in tools (18 tools in 6 categories)
# ═══════════════════════════════════════════════════════════════

BUILTIN_TOOLS = [
    # ── file ──
    {"name":"read_file", "category":"file", "summary":"读取文件内容",
     "tags":'["file","read"]', "description":"读取指定路径的文件，返回文本。支持绝对路径。",
     "parameters":'{"path":"string"}', "examples":'["read_file /tmp/test.txt"]'},
    {"name":"write_file", "category":"file", "summary":"写入文件",
     "tags":'["file","write"]', "description":"将内容写入指定路径，自动创建父目录。",
     "parameters":'{"path":"string","content":"string"}', "examples":'["write_file /tmp/out.txt\\nhello"]'},
    {"name":"edit_file", "category":"file", "summary":"编辑文件",
     "tags":'["file","edit"]', "description":"替换文件中old_str为new_str。old_str必须精确匹配。",
     "parameters":'{"path":"string","old_str":"string","new_str":"string"}', "examples":'["edit_file /tmp/x.py\\nold\\nnew"]'},
    {"name":"list_directory", "category":"file", "summary":"列出目录",
     "tags":'["file","list"]', "description":"列出指定目录的文件和子目录。",
     "parameters":'{"path":"string"}', "examples":'["list_directory /tmp"]'},

    # ── shell ──
    {"name":"run_command", "category":"shell", "summary":"执行Shell命令",
     "tags":'["shell","system"]', "description":"执行shell命令，超时30秒，返回stdout+stderr。",
     "parameters":'{"cmd":"string"}', "examples":'["run_command ls -la"]'},

    # ── memory ──
    {"name":"search_memory", "category":"memory", "summary":"搜索记忆库",
     "tags":'["memory","search"]', "description":"在MBclaw记忆库中全文搜索相关内容。",
     "parameters":'{"query":"string"}', "examples":'["search_memory 全文检索方案"]'},
    {"name":"list_sessions", "category":"memory", "summary":"列出会话",
     "tags":'["memory","list"]', "description":"列出最近的会话及其状态。",
     "parameters":'{}', "examples":'["list_sessions"]'},
    {"name":"get_session", "category":"memory", "summary":"查看会话",
     "tags":'["memory","detail"]', "description":"查看指定会话的消息和摘要。",
     "parameters":'{"session_id":"int"}', "examples":'["get_session 1"]'},

    # ── web ──
    {"name":"web_search", "category":"web", "summary":"网络搜索",
     "tags":'["web","search"]', "description":"搜索网络获取最新信息。",
     "parameters":'{"query":"string"}', "examples":'["web_search Python3.14新特性"]'},

    # ── browser ──
    {"name":"open_url", "category":"browser", "summary":"打开URL",
     "tags":'["browser","web"]', "description":"在浏览器中打开URL。",
     "parameters":'{"url":"string"}', "examples":'["open_url https://example.com"]'},

    # ── media ──
    {"name":"take_screenshot", "category":"media", "summary":"截图",
     "tags":'["media","screen"]', "description":"截取当前屏幕并保存。桌面环境需要支持。",
     "parameters":'{"path":"string"}', "examples":'["take_screenshot /tmp/screen.png"]'},

    # ── device ──
    {"name":"get_device_info", "category":"device", "summary":"设备信息",
     "tags":'["device","system"]', "description":"获取当前设备的基本信息。",
     "parameters":'{}', "examples":'["get_device_info"]'},
    {"name":"get_clipboard", "category":"device", "summary":"读取剪贴板",
     "tags":'["device","clipboard"]', "description":"读取系统剪贴板内容。",
     "parameters":'{}', "examples":'["get_clipboard"]'},
    {"name":"set_clipboard", "category":"device", "summary":"写入剪贴板",
     "tags":'["device","clipboard"]', "description":"将文本写入系统剪贴板。",
     "parameters":'{"text":"string"}', "examples":'["set_clipboard hello"]'},

    # ── classification ──
    {"name":"classify_content", "category":"classification", "summary":"内容分类",
     "tags":'["classification","ai"]', "description":"对文本内容进行分类，返回最匹配的分类标签。",
     "parameters":'{"text":"string"}', "examples":'["classify_content 这段代码有什么问题"]'},
    {"name":"extract_keywords", "category":"classification", "summary":"关键词提取",
     "tags":'["classification","nlp"]', "description":"使用jieba提取文本中的关键词。",
     "parameters":'{"text":"string"}', "examples":'["extract_keywords 使用SQLite FTS5做全文检索"]'},
    {"name":"summarize_text", "category":"classification", "summary":"文本摘要",
     "tags":'["classification","nlp"]', "description":"对文本进行摘要，提取关键信息。",
     "parameters":'{"text":"string"}', "examples":'["summarize_text 长文本内容..."]'},
]


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

def seed_tools(db: Session):
    for cfg in BUILTIN_TOOLS:
        if not db.query(Tool).filter(Tool.name == cfg["name"]).first():
            db.add(Tool(**cfg))
    db.commit()


def list_tools(db: Session, category: str = None, tag: str = None) -> list[dict]:
    """L1: list tools, optionally filtered."""
    seed_tools(db)
    q = db.query(Tool).order_by(Tool.usage_count.desc())
    if category: q = q.filter(Tool.category == category)
    if tag: q = q.filter(Tool.tags.contains(tag))
    return [{"id":t.id,"name":t.name,"category":t.category,"summary":t.summary,
             "tags":json.loads(t.tags),"usage_count":t.usage_count} for t in q.all()]


def get_tool(db: Session, tool_id: int) -> dict | None:
    """L3: full detail."""
    t = db.query(Tool).filter(Tool.id == tool_id).first()
    if not t: return None
    return {"id":t.id,"name":t.name,"category":t.category,"summary":t.summary,
            "description":t.description,"parameters":json.loads(t.parameters),
            "tags":json.loads(t.tags),"examples":json.loads(t.examples),"usage_count":t.usage_count}


def get_tool_by_name(db: Session, name: str) -> Optional["Tool"]:
    return db.query(Tool).filter(Tool.name == name).first()


def bump_usage(db: Session, tool_name: str):
    t = db.query(Tool).filter(Tool.name == tool_name).first()
    if t: t.usage_count += 1; db.commit()


def search_tools(db: Session, query: str, max_results: int = 10) -> list[dict]:
    """Search tools by name/description matching."""
    q = f"%{query}%"
    tools = db.query(Tool).filter(
        (Tool.name.ilike(q)) | (Tool.description.ilike(q)) | (Tool.tags.ilike(q))
    ).limit(max_results).all()
    return [{"id":t.id,"name":t.name,"summary":t.summary,"tags":json.loads(t.tags)} for t in tools]


# ═══════════════════════════════════════════════════════════════
# Execution engine
# ═══════════════════════════════════════════════════════════════

def execute(db: Session, tool_name: str, content: str) -> str:
    """Execute a tool by name with content as argument. Returns result string."""
    try:
        if tool_name == "read_file":
            path = content.strip()
            if not os.path.isabs(path): return f"需要绝对路径: {path}"
            if not os.path.exists(path): return f"文件不存在: {path}"
            with open(path) as f: text = f.read()
            return text[:5000] + (f"\n...(截断,共{len(text)}字)" if len(text)>5000 else "")

        elif tool_name == "write_file":
            parts = content.split('\n', 1)
            if len(parts)<2: return "需要 path\\ncontent 格式"
            path, body = parts[0].strip(), parts[1]
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path,'w') as f: f.write(body)
            return f"写入成功: {path} ({len(body)}字节)"

        elif tool_name == "edit_file":
            parts = content.split('\n---\n')
            if len(parts)<3: return "需要 path\\n---\\nold\\n---\\nnew 格式"
            path,old,new = parts[0].strip(), parts[1], parts[2]
            with open(path) as f: text = f.read()
            if old not in text: return "未找到要替换的文本"
            with open(path,'w') as f: f.write(text.replace(old, new, 1))
            return f"编辑成功: {path}"

        elif tool_name == "list_directory":
            path = content.strip() or '.'
            if not os.path.isdir(path): return f"不是目录: {path}"
            items = os.listdir(path)
            return "\n".join(f"{'[D]' if os.path.isdir(os.path.join(path,i)) else '[F]'} {i}" for i in sorted(items)[:100])

        elif tool_name == "run_command":
            r = subprocess.run(content, shell=True, capture_output=True, text=True, timeout=30)
            out = r.stdout + (f"\n[stderr]\n{r.stderr}" if r.stderr else "")
            return out[:3000] or f"(退出码:{r.returncode})"

        elif tool_name == "search_memory":
            from app.memory import MemoryRepo
            hits = MemoryRepo(db).query(content, top_n=5)
            return "\n".join(f"[#{h.session_id}] {h.summary[:200]} (score:{h.score:.2f})" for h in hits) or "未找到相关记忆"

        elif tool_name == "list_sessions":
            from app.models import Session as SM
            sessions = db.query(SM).order_by(SM.started_at.desc()).limit(20).all()
            return "\n".join(f"#{s.id} [{s.status}] {s.title}" for s in sessions) or "无会话"

        elif tool_name == "get_session":
            from app.models import Session as SM, Message
            try: sid = int(content.strip())
            except: return "需要 session_id"
            s = db.query(SM).filter(SM.id==sid).first()
            if not s: return f"会话{sid}不存在"
            msgs = db.query(Message).filter(Message.session_id==sid).order_by(Message.created_at).limit(20).all()
            lines = [f"#{s.id} [{s.status}] {s.title}"]
            for m in msgs: lines.append(f"  [{m.role}] {m.content[:100]}")
            return "\n".join(lines)

        elif tool_name == "web_search":
            return f"[web_search] 查询: {content[:200]} — 需要配置搜索API密钥"

        elif tool_name == "open_url":
            import webbrowser
            webbrowser.open(content.strip())
            return f"已打开: {content.strip()}"

        elif tool_name == "take_screenshot":
            path = content.strip() or "/tmp/screenshot.png"
            try:
                r = subprocess.run(["import","-window","root",path], capture_output=True, text=True, timeout=10)
                return f"截图保存: {path}" if os.path.exists(path) else f"截图失败: {r.stderr}"
            except: return "截图需要ImageMagick(import命令)"

        elif tool_name == "get_device_info":
            import platform
            return f"系统: {platform.system()} {platform.release()}\n处理器: {platform.processor()}\nPython: {platform.python_version()}"

        elif tool_name == "get_clipboard":
            try:
                r = subprocess.run(["xclip","-selection","clipboard","-o"], capture_output=True, text=True, timeout=5)
                return r.stdout[:2000] or "(剪贴板为空)"
            except: return "需要xclip: apt install xclip"

        elif tool_name == "set_clipboard":
            try:
                p = subprocess.Popen(["xclip","-selection","clipboard"], stdin=subprocess.PIPE)
                p.communicate(input=content.encode(), timeout=5)
                return "已复制到剪贴板"
            except: return "需要xclip: apt install xclip"

        elif tool_name == "classify_content":
            cats = ["技术选型","问题排查","功能开发","代码审查","项目规划","学习研究","闲聊"]
            text = content[:500].lower()
            if any(k in text for k in ["选型","用哪个","方案","技术","sql","数据库","框架"]): return "技术选型"
            if any(k in text for k in ["bug","报错","error","不行","错误","失败","修复"]): return "问题排查"
            if any(k in text for k in ["开发","实现","写","代码","功能","接口"]): return "功能开发"
            return "学习研究"

        elif tool_name == "extract_keywords":
            import jieba.analyse
            kws = jieba.analyse.extract_tags(content, topK=10, withWeight=True)
            return "\n".join(f"{kw} ({w:.2f})" for kw,w in kws)

        elif tool_name == "summarize_text":
            import jieba.analyse
            kws = jieba.analyse.extract_tags(content, topK=5)
            return f"关键词: {', '.join(kws)}\n前200字: {content[:200]}"

        else:
            return f"未知工具: {tool_name}"
    except Exception as e:
        return f"工具执行错误 [{tool_name}]: {e}"
