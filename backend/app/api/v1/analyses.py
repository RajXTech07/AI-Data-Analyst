import json
import re
from typing import Annotated
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.analysis import AnalysisOut, AnalyzeRequest, SteerRequest
from app.schemas.finding import FindingOut
from app.services.analyses import analysis_service
from app.services.datasets import dataset_service
from app.services.events import event_bus

from app.agent.orchestrator import run_analysis
from app.agent.llm import get_llm_client

router = APIRouter(tags=["analyses"])

@router.post("/datasets/{dataset_id}/analyze", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    dataset_id: uuid.UUID,
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = dataset_service.get_dataset(db, dataset_id, current_user.id)
    analysis = analysis_service.create_analysis(db, dataset, current_user.id, payload)
    
    # Queue autonomous agent investigation loop
    background_tasks.add_task(run_analysis, analysis.id)

    return analysis

@router.get("/analyses", response_model=list[AnalysisOut])
def list_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return analysis_service.list_analyses(db, current_user.id)

@router.get("/datasets/{dataset_id}/analyses", response_model=list[AnalysisOut])
def list_dataset_analyses(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return analysis_service.list_analyses(db, current_user.id, dataset_id=dataset_id)

@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return analysis_service.get_analysis(db, analysis_id, current_user.id)

@router.get("/analyses/{analysis_id}/charts")
def list_analysis_charts(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    charts = analysis_service.list_charts(db, analysis_id, current_user.id)
    return [
        {
            "id": c.id,
            "analysis_id": c.analysis_id,
            "finding_id": c.finding_id,
            "chart_type": c.chart_type,
            "spec": c.spec,
            "title": c.title
        }
        for c in charts
    ]

@router.post("/analyses/{analysis_id}/report", status_code=status.HTTP_202_ACCEPTED)
def generate_analysis_report(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = analysis_service.generate_report(db, analysis_id, current_user.id, format="html")
    return {
        "id": report.id,
        "analysis_id": report.analysis_id,
        "format": report.format,
        "download_url": f"/api/v1/reports/{report.id}/download?format=html",
        "created_at": report.created_at
    }

@router.get("/analyses/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify access
    analysis_service.get_analysis(db, analysis_id, current_user.id)

    async def event_generator():
        yield f"event: status\ndata: {json.dumps({'message': 'connected'})}\n\n"
        async for event in event_bus.subscribe(analysis_id):
            payload = json.dumps(event.data)
            yield f"event: {event.event}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.get("/analyses/{analysis_id}/findings", response_model=list[FindingOut])
def list_findings(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    findings = analysis_service.list_findings(db, analysis_id, current_user.id)
    out: list[FindingOut] = []
    for f in findings:
        evidence_ids = [e.tool_execution_id for e in f.evidence_links]
        chart_ids = [c.id for c in f.charts]
        out.append(
            FindingOut(
                id=f.id,
                title=f.title,
                observation=f.observation,
                statistical_evidence=f.statistical_evidence,
                interpretation=f.interpretation,
                limitations=f.limitations,
                hypothesis_status=f.hypothesis_status, # type: ignore
                confidence=f.confidence, # type: ignore
                evidence_execution_ids=evidence_ids,
                chart_ids=chart_ids
            )
        )
    return out

@router.get("/analyses/{analysis_id}/tool-executions")
def list_tool_executions(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    executions = analysis_service.list_tool_executions(db, analysis_id, current_user.id)
    return [
        {
            "id": e.id,
            "seq": e.seq,
            "tool_name": e.tool_name,
            "arguments": e.arguments,
            "result": e.result,
            "ok": e.ok,
            "error": e.error,
            "duration_ms": e.duration_ms,
            "source": e.source,
            "created_at": e.created_at
        }
        for e in executions
    ]

@router.post("/analyses/{analysis_id}/cancel", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def cancel_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return analysis_service.cancel_analysis(db, analysis_id, current_user.id)

@router.post("/analyses/{analysis_id}/steer", status_code=status.HTTP_202_ACCEPTED)
async def steer_analysis(
    analysis_id: uuid.UUID,
    payload: SteerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis_service.get_analysis(db, analysis_id, current_user.id)
    await event_bus.publish(analysis_id, "status", {"message": f"Steering received: {payload.instruction}"})
    return {"status": "accepted", "instruction": payload.instruction}

from app.core.logging import logger
from app.db.models.message import Message
from app.db.models.tool_execution import ToolExecution
from app.schemas.analysis import ChatMessageRequest, ChatMessageResponse, StructuredAnswer
from app.services.chat_engine import chat_engine

@router.post("/analyses/{analysis_id}/chat", response_model=ChatMessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def chat_followup(
    analysis_id: uuid.UUID,
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req_id = str(uuid.uuid4())[:8]
    analysis = analysis_service.get_analysis(db, analysis_id, current_user.id)
    dataset = dataset_service.get_dataset(db, analysis.dataset_id, current_user.id)
    df = dataset_service.load_dataframe(dataset, cleaned=True)

    # 1. Store user message
    user_msg = Message(
        analysis_id=analysis_id,
        role="user",
        content=payload.message
    )
    db.add(user_msg)
    db.commit()

    # 2. Process query via structured ChatEngine
    try:
        structured: StructuredAnswer = chat_engine.process_chat(
            db=db,
            analysis_id=analysis_id,
            dataset=dataset,
            df=df,
            user_message=payload.message,
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"[Chat Req {req_id}] Unexpected error processing message: {str(e)}", exc_info=True)
        structured = StructuredAnswer(
            answer="I could not answer that. Please try again or rephrase.",
            key_points=[
                "The query could not be executed on the current dataset.",
                "Try asking about column importance or excluding incomplete rows."
            ],
            numbers=[],
            cautions=["Check the query parameters and available column names."],
            next_questions=["Which columns matter most?", "What if I exclude incomplete rows?"],
            calc_ids=[],
            data_version="cleaned",
            confidence="low"
        )

    # 3. Store assistant message with structured answer
    # Format full scannable markdown content
    md_parts = [structured.answer]
    if structured.key_points:
        md_parts.append("\n".join(f"- {kp}" for kp in structured.key_points))
    if structured.numbers:
        table_rows = ["| Metric / Column | Value | Note |", "| :--- | :--- | :--- |"]
        for row in structured.numbers:
            table_rows.append(f"| {row.get('label', '')} | {row.get('value', '')} | {row.get('note', '')} |")
        md_parts.append("\n".join(table_rows))
    if structured.cautions:
        md_parts.append("\n".join(f"> {c}" for c in structured.cautions))
    
    full_content = "\n\n".join(md_parts)

    asst_msg = Message(
        analysis_id=analysis_id,
        role="assistant",
        content=json.dumps(structured.model_dump()),
        tool_execution_ids=structured.calc_ids
    )
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    # Emit message event
    await event_bus.publish(analysis_id, "message_delta", {
        "message_id": str(asst_msg.id),
        "text": full_content,
        "structured_answer": structured.model_dump()
    })

    return ChatMessageResponse(
        message_id=asst_msg.id,
        role="assistant",
        content=full_content,
        structured_answer=structured,
        tool_execution_ids=structured.calc_ids
    )

@router.get("/analyses/{analysis_id}/messages")
def get_chat_history(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis_service.get_analysis(db, analysis_id, current_user.id)
    stmt = select(Message).where(Message.analysis_id == analysis_id).order_by(Message.created_at.asc())
    msgs = db.scalars(stmt).all()
    out = []
    for m in msgs:
        structured = None
        content = m.content
        if m.role == "assistant" and content.strip().startswith("{"):
            try:
                parsed = json.loads(content)
                if "answer" in parsed:
                    structured = parsed
                    content = parsed.get("answer", content)
            except Exception:
                pass
        out.append({
            "id": m.id,
            "role": m.role,
            "content": content,
            "structured_answer": structured,
            "tool_execution_ids": m.tool_execution_ids or [],
            "created_at": m.created_at
        })
    return out
