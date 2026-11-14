import asyncio
from datetime import datetime, timezone
from typing import Any
import uuid
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.interpreter import write_findings
from app.agent.llm import get_llm_client
from app.agent.planner import make_plan
from app.agent.prompts import SYSTEM_PROMPT, make_step_tool_prompt
from app.agent.validator import validator
from app.core.config import settings
from app.core.logging import logger
from app.db.models.analysis import Analysis
from app.db.models.chart import Chart
from app.db.models.dataset import Dataset
from app.db.models.finding import Finding, FindingEvidence
from app.db.models.tool_execution import ToolExecution
from app.db.session import SessionLocal
from app.schemas.analysis import InvestigationPlan, PlanStep
from app.schemas.dataset import DatasetProfile
from app.schemas.finding import StatEvidence
from app.services.datasets import dataset_service
from app.services.events import event_bus
from app.tools import REGISTRY, llm_tool_schemas, run_tool

def execute_planned_step(
    step: PlanStep,
    df: pd.DataFrame,
    profile: DatasetProfile,
    llm: Any,
    prior_context: str = ""
) -> tuple[str, dict[str, Any]]:
    """
    Executes a planned investigation step.
    Fast path: If the planner specified a registered tool and valid arguments, executes instantly (0ms network).
    Heuristic path: If arguments are missing or invalid, deterministically resolves parameters instantly (<1ms).
    LLM path: If tool name is unknown, queries the LLM via function calling.
    """
    tool_name = step.suggested_tool or ""
    tool_args = step.tool_args or {}

    col_names = set(df.columns)
    num_cols = [c.name for c in profile.columns if c.dtype == "numeric"]
    cat_cols = [c.name for c in profile.columns if c.dtype in ["categorical", "boolean"]]
    date_cols = [c.name for c in profile.columns if c.dtype == "datetime"]

    # 1. Fast path: check if planner gave a valid registered tool and valid arguments
    if tool_name in REGISTRY:
        valid = True
        if "column" in tool_args and tool_args["column"] not in col_names:
            valid = False
        if "columns" in tool_args and tool_args["columns"]:
            if not all(c in col_names for c in tool_args["columns"]):
                valid = False
        if "group_column" in tool_args and tool_args["group_column"] not in col_names:
            valid = False
        if "metric_column" in tool_args and tool_args["metric_column"] not in col_names:
            valid = False
        if "value_column" in tool_args and tool_args["value_column"] not in col_names:
            valid = False
        if "date_column" in tool_args and tool_args["date_column"] not in col_names:
            valid = False

        if valid and (tool_args or tool_name in ("profile_dataset", "detect_duplicates")):
            logger.info(f"Fast path: Executing planned tool '{tool_name}' with arguments: {tool_args}")
            return tool_name, tool_args

        # 2. Heuristic resolution path: tool is known, fill missing or invalid arguments
        args: dict[str, Any] = {}
        if tool_name == "calculate_statistics":
            args = {"columns": num_cols[:4] if num_cols else list(df.columns[:2])}
        elif tool_name == "group_by_analysis":
            if cat_cols and num_cols:
                args = {"group_column": cat_cols[0], "metric_column": num_cols[0], "aggregation": "mean"}
            else:
                tool_name = "calculate_statistics"
                args = {"columns": num_cols[:2] if num_cols else list(df.columns[:2])}
        elif tool_name == "correlation_analysis":
            args = {"columns": num_cols[:4] if len(num_cols) >= 2 else None, "method": "pearson"}
        elif tool_name == "statistical_test":
            if cat_cols and num_cols:
                args = {"group_column": cat_cols[0], "value_column": num_cols[0], "test_type": "auto"}
            elif len(num_cols) >= 2:
                args = {"value_column": num_cols[0], "second_column": num_cols[1], "test_type": "correlation"}
            else:
                tool_name = "calculate_statistics"
                args = {"columns": num_cols[:2] if num_cols else list(df.columns[:2])}
        elif tool_name == "detect_outliers":
            args = {"column": num_cols[0] if num_cols else df.columns[0], "method": "iqr"}
        elif tool_name == "detect_missing_values":
            args = {"columns": list(df.columns)}
        elif tool_name == "detect_duplicates":
            args = {"subset": None}
        elif tool_name == "trend_analysis":
            if date_cols and num_cols:
                args = {"date_column": date_cols[0], "value_column": num_cols[0], "freq": "M"}
            else:
                tool_name = "calculate_statistics"
                args = {"columns": num_cols[:2] if num_cols else list(df.columns[:2])}
        else:
            args = {}
        logger.info(f"Heuristic path: Resolved parameters for '{tool_name}': {args}")
        return tool_name, args

    # 3. Fallback path: Only query LLM via function calling if tool was unrecognized
    try:
        cols_desc = [f"- '{c.name}' ({c.dtype})" for c in profile.columns]
        columns_summary = "\n".join(cols_desc)
        step_prompt = make_step_tool_prompt(
            step_goal=step.goal,
            hypothesis=step.hypothesis,
            suggested_tool=step.suggested_tool,
            context_summary=prior_context or "Initial investigation step.",
            columns_summary=columns_summary
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": step_prompt}
        ]
        schemas = llm_tool_schemas()
        response = llm.generate(messages=messages, tools=schemas)

        if response.tool_calls:
            chosen_call = response.tool_calls[0]
            if chosen_call.name in REGISTRY:
                logger.info(f"LLM autonomously selected tool '{chosen_call.name}' with arguments: {chosen_call.arguments}")
                return chosen_call.name, chosen_call.arguments
    except Exception as e:
        logger.warning(f"LLM tool selection encountered an issue, falling back to heuristics: {str(e)}")

    # Ultimate fallback
    return "calculate_statistics", {"columns": num_cols[:4] if num_cols else list(df.columns[:2])}

async def run_analysis(analysis_id: uuid.UUID, force_mock_llm: bool = False) -> None:
    """Main autonomous investigation loop executing the plan and generating findings."""
    db: Session = SessionLocal()
    llm = get_llm_client(force_mock=force_mock_llm)

    try:
        stmt = select(Analysis).where(Analysis.id == analysis_id)
        analysis = db.scalar(stmt)
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return

        dataset = db.get(Dataset, analysis.dataset_id)
        if not dataset:
            logger.error(f"Dataset {analysis.dataset_id} not found for analysis {analysis_id}")
            return

        # 1. Start Analysis
        analysis.status = "running"
        analysis.started_at = datetime.now(timezone.utc)
        db.commit()
        await event_bus.publish(analysis_id, "status", {"status": "running", "message": "Investigation started."})

        # Load dataset
        profile = DatasetProfile.model_validate(dataset.profile)
        df = await asyncio.to_thread(dataset_service.load_dataframe, dataset, cleaned=True)

        # 2. Planning Phase
        await event_bus.publish(analysis_id, "status", {"status": "planning", "message": "Formulating investigation plan..."})
        plan: InvestigationPlan = await asyncio.to_thread(make_plan, profile, analysis.question, llm)
        analysis.plan = plan.model_dump()
        db.commit()
        await event_bus.publish(analysis_id, "plan", {"steps": [s.model_dump() for s in plan.steps]})

        # 3. Execution Loop
        tool_executions: list[ToolExecution] = []
        tool_results_by_id: dict[uuid.UUID, dict[str, Any]] = {}
        seq = 1

        for step in plan.steps:
            # Yield event loop so concurrent polling HTTP requests are answered immediately
            await asyncio.sleep(0.02)

            # Check for cancellation or limit
            db.refresh(analysis)
            if analysis.status == "cancelled":
                logger.info(f"Analysis {analysis_id} was cancelled by user.")
                break
            if seq > settings.LLM_MAX_TOOL_CALLS:
                logger.info("Tool execution budget limit reached.")
                break

            context_summary = f"Executed {len(tool_executions)} tools so far. Last tool: {tool_executions[-1].tool_name if tool_executions else 'None'}."
            tool_name, tool_args = await asyncio.to_thread(
                execute_planned_step, step, df, profile, llm, prior_context=context_summary
            )

            await event_bus.publish(
                analysis_id,
                "tool_started",
                {"seq": seq, "tool_name": tool_name, "arguments": tool_args, "goal": step.goal}
            )

            # Pure tool execution offloaded to worker thread to prevent event loop starvation
            result = await asyncio.to_thread(run_tool, tool_name, tool_args, df)

            execution = ToolExecution(
                analysis_id=analysis_id,
                seq=seq,
                tool_name=tool_name,
                arguments=tool_args,
                result=result.data if result.ok else None,
                ok=result.ok,
                error=result.error,
                duration_ms=result.duration_ms,
                source="agent"
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)

            tool_executions.append(execution)
            tool_results_by_id[execution.id] = {"data": result.data, "error": result.error}

            await event_bus.publish(
                analysis_id,
                "tool_finished",
                {
                    "seq": seq,
                    "tool_name": tool_name,
                    "ok": result.ok,
                    "duration_ms": result.duration_ms,
                    "summary": f"Completed step: {step.goal}"
                }
            )

            if step.hypothesis:
                hypo_status = "supported" if result.ok else "inconclusive"
                await event_bus.publish(
                    analysis_id,
                    "hypothesis",
                    {"statement": step.hypothesis, "status": hypo_status}
                )

            seq += 1

        # 4. Interpretation & Finding Drafting
        await event_bus.publish(analysis_id, "status", {"status": "interpreting", "message": "Synthesizing evidence and grounding numbers..."})
        finding_drafts = await asyncio.to_thread(write_findings, tool_executions, llm)

        # 5. Validation, Grounding & Persistence
        rank = 1
        for draft in finding_drafts:
            # Verify numeric grounding against tool outputs
            is_grounded, grounding_warnings = validator.verify_grounding(draft, tool_results_by_id)

            # Extract statistical evidence if applicable
            stat_ev = StatEvidence()
            for eid in draft.evidence_execution_ids:
                t_exec = next((e for e in tool_executions if e.id == eid), None)
                if t_exec and t_exec.tool_name == "statistical_test" and isinstance(t_exec.result, dict):
                    t_data = t_exec.result
                    stat_ev = StatEvidence(
                        test=t_data.get("test"),
                        statistic=t_data.get("statistic"),
                        p_value=t_data.get("p_value"),
                        effect_size=t_data.get("effect_size"),
                        n=t_data.get("total_n"),
                        assumptions=t_data.get("assumptions")
                    )
                elif t_exec and t_exec.tool_name == "correlation_analysis" and isinstance(t_exec.result, dict):
                    t_data = t_exec.result
                    ranked = t_data.get("ranked_pairs", [])
                    if ranked:
                        top = ranked[0]
                        stat_ev = StatEvidence(
                            test=f"{top.get('method', 'Pearson').capitalize()} correlation",
                            statistic=top.get("correlation"),
                            p_value=top.get("p_value"),
                            effect_size=top.get("correlation"),
                            n=top.get("n")
                        )

            confidence = validator.compute_confidence(
                hypothesis_status=draft.hypothesis_status,
                stat_evidence=stat_ev,
                warnings=grounding_warnings
            )

            limitations_text = draft.limitations
            if grounding_warnings:
                limitations_text += " Note: " + "; ".join(grounding_warnings)

            finding = Finding(
                analysis_id=analysis_id,
                title=draft.title,
                observation=draft.observation,
                statistical_evidence=stat_ev.model_dump(),
                interpretation=draft.interpretation,
                limitations=limitations_text,
                hypothesis_status=draft.hypothesis_status,
                confidence=confidence,
                rank=rank
            )
            db.add(finding)
            db.commit()
            db.refresh(finding)

            # Link evidence
            for eid in draft.evidence_execution_ids:
                link = FindingEvidence(finding_id=finding.id, tool_execution_id=eid)
                db.add(link)

            # Automatically generate an interactive Plotly chart for significant findings
            if stat_ev.test or draft.hypothesis_status in ["supported", "descriptive"]:
                num_cols = [c.name for c in profile.columns if c.dtype == "numeric"]
                cat_cols = [c.name for c in profile.columns if c.dtype in ["categorical", "boolean"]]
                date_cols = [c.name for c in profile.columns if c.dtype == "datetime"]

                chart_type = None
                chart_args = {}

                # 1. Evidence-guided chart selection
                matched_exec = None
                for eid in draft.evidence_execution_ids:
                    for ex in tool_executions:
                        if ex.id == eid:
                            matched_exec = ex
                            break
                    if matched_exec:
                        break

                if matched_exec:
                    args = matched_exec.arguments or {}
                    if matched_exec.tool_name == "correlation_analysis":
                        cols = args.get("columns", [])
                        if cols and len(cols) >= 2:
                            chart_type = "scatter"
                            chart_args = {"chart_type": "scatter", "x": cols[0], "y": cols[1], "title": finding.title}
                    elif matched_exec.tool_name == "group_by_analysis":
                        grp = args.get("group_column")
                        met = args.get("metric_column")
                        if grp and met:
                            chart_type = "bar"
                            chart_args = {"chart_type": "bar", "x": grp, "y": met, "title": finding.title}
                    elif matched_exec.tool_name == "statistical_test":
                        grp = args.get("group_column")
                        val = args.get("value_column")
                        if grp and val:
                            chart_type = "box"
                            chart_args = {"chart_type": "box", "x": grp, "y": val, "title": finding.title}
                    elif matched_exec.tool_name == "trend_analysis":
                        dcol = args.get("date_column")
                        val = args.get("value_column")
                        if dcol and val:
                            chart_type = "line"
                            chart_args = {"chart_type": "line", "x": dcol, "y": val, "title": finding.title}

                # 2. Schema-based fallback chart selection
                if not chart_type or not chart_args:
                    if date_cols and num_cols:
                        chart_type = "line"
                        chart_args = {"chart_type": "line", "x": date_cols[0], "y": num_cols[0], "title": finding.title}
                    elif cat_cols and num_cols:
                        chart_type = "bar"
                        chart_args = {"chart_type": "bar", "x": cat_cols[0], "y": num_cols[0], "title": finding.title}
                    elif len(num_cols) >= 2:
                        chart_type = "scatter"
                        chart_args = {"chart_type": "scatter", "x": num_cols[0], "y": num_cols[1], "title": finding.title}
                    elif num_cols:
                        chart_type = "histogram"
                        chart_args = {"chart_type": "histogram", "x": num_cols[0], "title": finding.title}
                    elif cat_cols:
                        chart_type = "bar"
                        chart_args = {"chart_type": "bar", "x": cat_cols[0], "title": finding.title}

                if chart_type and chart_args:
                    chart_res = run_tool("generate_chart", chart_args, df)
                    if chart_res.ok and chart_res.data:
                        chart = Chart(
                            analysis_id=analysis_id,
                            finding_id=finding.id,
                            chart_type=chart_type,
                            spec=chart_res.data["spec"],
                            title=finding.title
                        )
                        db.add(chart)
                        db.commit()
                        await event_bus.publish(analysis_id, "chart", {"id": str(chart.id), "title": chart.title})

            db.commit()
            await event_bus.publish(analysis_id, "finding", {"id": str(finding.id), "title": finding.title, "confidence": confidence})
            rank += 1

        # 6. Mark Completed
        analysis.status = "completed"
        analysis.finished_at = datetime.now(timezone.utc)
        db.commit()
        await event_bus.publish(analysis_id, "done", {"status": "completed"})
        logger.info(f"Analysis {analysis_id} finished successfully with {rank - 1} findings.")

    except Exception as e:
        logger.error(f"Error in run_analysis {analysis_id}: {str(e)}", exc_info=True)
        try:
            analysis.status = "failed"
            analysis.error = str(e)
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()
            await event_bus.publish(analysis_id, "error", {"message": str(e)})
            await event_bus.publish(analysis_id, "done", {"status": "failed"})
        except Exception:
            pass
    finally:
        db.close()
        await event_bus.close(analysis_id)
