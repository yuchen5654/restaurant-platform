from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.services.llm_service import ask_restaurant_question

router = APIRouter(prefix='/ai', tags=['ai'])


class QuestionRequest(BaseModel):
    question:             str
    conversation_history: list[dict] = []


@router.post('/ask')
def ask(
    req: QuestionRequest,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    if not req.question.strip():
        raise HTTPException(400, 'question must not be empty')
    try:
        answer = ask_restaurant_question(db, rid, req.question, req.conversation_history)
        return {'answer': answer}
    except Exception as exc:
        raise HTTPException(502, f'LLM service error: {exc}') from exc
