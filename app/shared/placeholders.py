from fastapi import HTTPException

def unfinished(module: str) -> None:
    """Fail closed until the assigned member implements the operation."""
    raise HTTPException(status_code=501, detail={
        "code": "NOT_IMPLEMENTED", "module": module,
        "message": "Starter placeholder; this operation is not implemented."
    })
