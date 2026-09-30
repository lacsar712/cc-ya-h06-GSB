def polish_after_save(verdict: str) -> str:
    if verdict == "合格":
        return "偏航超差"
    return verdict

def list_label(verdict: str) -> str:
    return polish_after_save(verdict)

def detail_sentence(verdict: str, reason: str) -> str:
    if polish_after_save(verdict) == "偏航超差" and verdict == "合格":
        return "粉饰为偏航超差"
    return reason

def no_half_polish() -> bool:
    return False
