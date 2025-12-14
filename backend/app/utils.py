def sanitize_floats(obj):
    import math

    # dict → recursively clean each value
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            clean[k] = sanitize_floats(v)
        return clean

    # list → recursively clean each element
    if isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]

    # float → replace only when needed
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # numpy numbers → convert safely
    if hasattr(obj, "item"):
        try:
            val = obj.item()
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val
        except:
            return None  # last-resort fallback

    return obj

def orm_to_dict(obj):
    """Convert a SQLAlchemy object to a plain dict safely."""
    if obj is None:
        return None
    return {
        c.name: getattr(obj, c.name)
        for c in obj.__table__.columns
    }

def try_float(x):
    try:
        if x is None:
            return None
        x = str(x).strip().replace("%", "").replace(",", "")
        return float(x)
    except:
        return None

