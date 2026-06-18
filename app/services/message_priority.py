"""Project 7: Message Priority — new message = new task, old task→background.

Default MBclaw behavior: new user message always interrupts current task.
No /stop command needed (key difference from OpenClaw).
"""


def is_new_topic(current_task_name: str, new_message: str) -> bool:
    """Heuristic: check if new message is a different topic from active task.

    Simple keyword overlap check. Can be upgraded to LLM semantic comparison.
    """
    if not current_task_name:
        return True

    current_words = set(_tokenize(current_task_name))
    msg_words = set(_tokenize(new_message))

    if not current_words or not msg_words:
        return True

    overlap = len(current_words & msg_words)
    total = min(len(current_words), len(msg_words)) or 1
    similarity = overlap / total

    # Below 30% keyword overlap → new topic
    return similarity < 0.3


def _tokenize(text: str) -> list[str]:
    import re
    return re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())


def decide_interrupt(current_task_name: str, new_message: str) -> dict:
    """Decide whether to interrupt current task for new message.

    Returns:
      {interrupt: bool, reason: str, suspend_checkpoint: bool}
    """
    new = is_new_topic(current_task_name, new_message)
    if new:
        return {
            "interrupt": True,
            "reason": "新消息属于不同主题，当前任务转入后台",
            "suspend_checkpoint": True,
        }
    return {
        "interrupt": False,
        "reason": "消息与当前任务相关，继续执行",
        "suspend_checkpoint": False,
    }
