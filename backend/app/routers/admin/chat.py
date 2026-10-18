"""관리자 API: AI 챗봇 (성호). 대화방·메시지는 DB 에 저장하고 답변은 제미나이가 만든다."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings
from app.services.chat import GREETING, ChatService, ChatUnavailable
from app.stores.chat import TITLE_MAX, ChatStore
from app.stores.stats import StatsStore

router = APIRouter()


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


def _store(request: Request, settings: Settings) -> ChatStore:
    """CHAT_OWNER_ID 가 비어 있으면 대화방 주인을 정할 수 없으므로 500 대신 안내 오류를 돌려준다."""
    if not settings.chat_owner_id:
        raise HTTPException(503, "CHAT_OWNER_ID 설정이 필요합니다.")
    return ChatStore(request.app.state.db, settings.chat_owner_id)


def _session(store: ChatStore, session_id: str) -> dict:
    """없는 대화방이면 404. uuid 모양이 아닌 id 도 DB 오류가 나지 않게 같은 404 로 처리한다."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return session


@router.post("/marketing/chat/sessions", status_code=201)
def create_session(request: Request, settings: Settings = Depends(get_settings)):
    store = _store(request, settings)
    session_id = store.create_session()
    store.add_messages(session_id, [("assistant", GREETING)])  # 첫 인사 메시지
    return store.get_session(session_id)


@router.get("/marketing/chat/sessions")
def list_sessions(request: Request, settings: Settings = Depends(get_settings)):
    return _store(request, settings).list_sessions()


@router.get("/marketing/chat/sessions/{session_id}")
def get_session(session_id: str, request: Request, settings: Settings = Depends(get_settings)):
    return _session(_store(request, settings), session_id)


@router.delete("/marketing/chat/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request, settings: Settings = Depends(get_settings)):
    store = _store(request, settings)
    _session(store, session_id)  # 없으면 404
    store.delete_session(session_id)
    return Response(status_code=204)


@router.post("/marketing/chat/sessions/{session_id}/messages", status_code=201)
def send_message(session_id: str, body: MessageIn, request: Request, settings: Settings = Depends(get_settings)):
    """질문을 받아 답변을 만들고 질문·답변을 함께 저장한다. 답변 생성이 실패하면 아무것도 저장하지 않는다."""
    store = _store(request, settings)
    session = _session(store, session_id)
    question = body.content.strip()
    if not question:
        raise HTTPException(422, "질문을 입력해 주세요.")
    service = ChatService(settings, StatsStore(request.app.state.db), request.app.state.members)
    try:
        answer = service.answer(session["messages"], question)
    except ChatUnavailable as e:
        raise HTTPException(502, str(e))
    store.add_messages(session_id, [("user", question), ("assistant", answer)])
    if len(session["messages"]) <= 1:  # 첫 질문이면 질문 앞부분을 대화방 제목으로 쓴다
        store.set_title(session_id, question[:TITLE_MAX])
    return {"messages": store.messages(session_id)[-2:]}
