"""缺口2: LLM输出 schema 校验 — 防止格式漂移"""
import json, jsonschema

MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "episodes": {
            "type": "array", "maxItems": 3,
            "items": {"type": "object", "properties": {
                "goal": {"type": "string"}, "decision": {"type": "string"},
                "result": {"type": "string"}, "tags": {"type": "array"}
            }}
        },
        "semantics": {
            "type": "array", "maxItems": 3,
            "items": {"type": "object", "properties": {
                "topic": {"type": "string"}, "facts": {"type": "array"},
                "tags": {"type": "array"}
            }}
        },
        "procedures": {
            "type": "array", "maxItems": 2,
            "items": {"type": "object", "properties": {
                "task": {"type": "string"}, "steps": {"type": "array"},
                "prerequisites": {"type": "array"},
                "expected_outcome": {"type": "string"}, "tags": {"type": "array"}
            }}
        },
        "failures": {
            "type": "array", "maxItems": 2,
            "items": {"type": "object", "properties": {
                "task": {"type": "string"}, "attempt": {"type": "string"},
                "why_failed": {"type": "string"}, "lesson": {"type": "string"},
                "tags": {"type": "array"}
            }}
        }
    }
}

def validate_memory_output(raw_json_str):
    """校验 MemoryEncoder 输出, 返回 (is_valid, errors)"""
    try:
        data = json.loads(raw_json_str)
        jsonschema.validate(data, MEMORY_SCHEMA)
        return True, []
    except json.JSONDecodeError as e:
        return False, [f"JSON parse error: {e}"]
    except jsonschema.ValidationError as e:
        return False, [f"Schema violation: {e.message} at {'.'.join(str(p) for p in e.path)}"]

def safe_parse(raw_json_str):
    """安全解析, 不符合schema的字段丢弃, 不崩溃"""
    try:
        data = json.loads(raw_json_str)
    except:
        return {"episodes": [], "semantics": [], "procedures": [], "failures": []}
    
    result = {"episodes": [], "semantics": [], "procedures": [], "failures": []}
    for key in result:
        items = data.get(key, [])
        if isinstance(items, list):
            result[key] = items[:3]  # 限制数量
    return result
