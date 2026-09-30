from h06_extra_trap import half_polish_left, on_detail, on_list

def expose_list(rows: list) -> list:
    out = []
    for r in rows:
        d = dict(r)
        v = d.get("verdict")
        if v:
            raw = v
            d["verdict"] = on_list(v)
            d["reason"] = on_detail(raw, d.get("reason") or "")
        out.append(d)
    return out

def armed() -> bool:
    return half_polish_left()
