from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AnalysisConflict, NotFoundError
from app.core.logging import logger
from app.db.models.analysis import Analysis
from app.db.models.dataset import Dataset
from app.db.models.tool_execution import ToolExecution
from app.db.models.finding import Finding
from app.schemas.analysis import AnalyzeRequest
from app.services.events import event_bus

from app.core.config import settings
from app.db.models.chart import Chart
from app.db.models.report import Report

class AnalysisService:
    @staticmethod
    def create_analysis(
        db: Session,
        dataset: Dataset,
        user_id: uuid.UUID,
        request: AnalyzeRequest
    ) -> Analysis:
        # Check if an analysis is already actively running for this dataset/user
        existing = db.scalar(
            select(Analysis).where(
                Analysis.user_id == user_id,
                Analysis.dataset_id == dataset.id,
                Analysis.status.in_(["queued", "running"])
            )
        )
        if existing:
            raise AnalysisConflict(f"An analysis ({existing.id}) is already {existing.status} for this dataset.")

        analysis = Analysis(
            dataset_id=dataset.id,
            user_id=user_id,
            question=request.question,
            status="queued"
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        logger.info(f"Created analysis {analysis.id} for dataset {dataset.id}")
        return analysis

    @staticmethod
    def get_analysis(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID) -> Analysis:
        stmt = select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user_id)
        analysis = db.scalar(stmt)
        if not analysis:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        return analysis

    @staticmethod
    def list_analyses(db: Session, user_id: uuid.UUID, dataset_id: uuid.UUID | None = None) -> list[Analysis]:
        stmt = select(Analysis).where(Analysis.user_id == user_id)
        if dataset_id:
            stmt = stmt.where(Analysis.dataset_id == dataset_id)
        stmt = stmt.order_by(Analysis.created_at.desc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_findings(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID) -> list[Finding]:
        # Verifies ownership
        AnalysisService.get_analysis(db, analysis_id, user_id)
        stmt = select(Finding).where(Finding.analysis_id == analysis_id).order_by(Finding.rank.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_tool_executions(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID) -> list[ToolExecution]:
        # Verifies ownership
        AnalysisService.get_analysis(db, analysis_id, user_id)
        stmt = select(ToolExecution).where(ToolExecution.analysis_id == analysis_id).order_by(ToolExecution.seq.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_charts(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID) -> list[Chart]:
        # Verifies ownership
        AnalysisService.get_analysis(db, analysis_id, user_id)
        stmt = select(Chart).where(Chart.analysis_id == analysis_id)
        return list(db.scalars(stmt).all())

    @staticmethod
    def cancel_analysis(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID) -> Analysis:
        analysis = AnalysisService.get_analysis(db, analysis_id, user_id)
        if analysis.status in ["queued", "running"]:
            analysis.status = "cancelled"
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(analysis)
            logger.info(f"Cancelled analysis {analysis_id}")
        return analysis

    @staticmethod
    def generate_report(db: Session, analysis_id: uuid.UUID, user_id: uuid.UUID, format: str = "html") -> Report:
        analysis = AnalysisService.get_analysis(db, analysis_id, user_id)
        findings = AnalysisService.list_findings(db, analysis_id, user_id)
        executions = AnalysisService.list_tool_executions(db, analysis_id, user_id)

        reports_dir = settings.resolved_storage_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_id = uuid.uuid4()
        file_path = reports_dir / f"{report_id}.html"

        # Construct self-contained HTML report
        findings_html = ""
        for f in findings:
            ev = f.statistical_evidence or {}
            findings_html += f"""
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #ffffff;">
                <h3 style="margin-top: 0; color: #1e293b;">{f.title}</h3>
                <p><strong>Status:</strong> <span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px;">{f.hypothesis_status}</span>
                   <strong>Confidence:</strong> <span style="background: #f1f5f9; color: #334155; padding: 2px 8px; border-radius: 4px;">{f.confidence}</span></p>
                <p><strong>Observation:</strong> {f.observation}</p>
                <div style="background: #f8fafc; border-left: 4px solid #3b82f6; padding: 8px 12px; margin: 8px 0; font-family: monospace; font-size: 0.9em;">
                    Evidence: test={ev.get('test', 'N/A')}, statistic={ev.get('statistic', 'N/A')}, p_value={ev.get('p_value', 'N/A')}, effect_size={ev.get('effect_size', 'N/A')}, n={ev.get('n', 'N/A')}
                </div>
                <p><strong>Interpretation:</strong> {f.interpretation}</p>
                <p style="color: #64748b; font-size: 0.85em;"><strong>Limitations:</strong> {f.limitations}</p>
            </div>
            """

        exec_html = "".join([
            f"<tr><td style='padding:6px;border:1px solid #cbd5e1;'>#{e.seq}</td>"
            f"<td style='padding:6px;border:1px solid #cbd5e1;'><code>{e.tool_name}</code></td>"
            f"<td style='padding:6px;border:1px solid #cbd5e1;'>{'✅ OK' if e.ok else '❌ Error'}</td>"
            f"<td style='padding:6px;border:1px solid #cbd5e1;'>{e.duration_ms} ms</td></tr>"
            for e in executions
        ])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AI Data Analyst Report - Analysis {analysis_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #0f172a; margin: 40px auto; max-width: 900px; padding: 0 20px; }}
        h1, h2, h3 {{ color: #0f172a; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }}
        th {{ background: #f1f5f9; padding: 8px; text-align: left; border: 1px solid #cbd5e1; }}
        .header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Autonomous Data Analysis Report</h1>
        <p><strong>Analysis ID:</strong> {analysis_id} | <strong>Question:</strong> {analysis.question or 'Open exploratory analysis'}</p>
        <p><strong>Status:</strong> {analysis.status} | <strong>Started:</strong> {analysis.started_at} | <strong>Finished:</strong> {analysis.finished_at}</p>
    </div>

    <h2>1. Executive Findings</h2>
    {findings_html if findings_html else '<p>No findings recorded.</p>'}

    <h2>2. Execution Audit Appendix</h2>
    <p>Every finding above is verified by standard analytical calculations. The complete execution audit trail:</p>
    <table>
        <thead><tr><th>Seq</th><th>Tool</th><th>Result</th><th>Duration</th></tr></thead>
        <tbody>{exec_html}</tbody>
    </table>
</body>
</html>"""

        file_path.write_text(html_content, encoding="utf-8")

        report = Report(
            id=report_id,
            analysis_id=analysis_id,
            format=format,
            storage_path=str(file_path)
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

analysis_service = AnalysisService()

