import uuid
from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_team_id_var: ContextVar[str] = ContextVar("team_id", default="")
_model_requested_var: ContextVar[str] = ContextVar("model_requested", default="")


def generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_team_id() -> str:
    return _team_id_var.get()


def set_team_id(team_id: str) -> None:
    _team_id_var.set(team_id)


def get_model_requested() -> str:
    return _model_requested_var.get()


def set_model_requested(model_requested: str) -> None:
    _model_requested_var.set(model_requested)
