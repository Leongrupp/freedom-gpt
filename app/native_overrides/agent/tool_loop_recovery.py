"""Bounded strategy changes after a tool loop, gated by the live full-access policy.

Guidance is part of the current tool result before persistence. No fabricated user
turn, automatic resubmission, history rewrite or permission change is needed.
"""

from __future__ import annotations

import logging

from agent.tool_guardrails import append_toolguard_guidance, toolguard_synthetic_result
from hermes_cli.observability.shared_metrics_harness import record_guardrail_decision, record_guardrail_warnings

logger = logging.getLogger(__name__)
MAX_STRATEGY_RECOVERIES = 3
RECOVERABLE_LOOP_CODES = frozenset({
    "repeated_exact_failure_block", "idempotent_no_progress_block", "same_tool_failure_halt",
    "identical_call_streak_halt", "identical_cycle_halt", "auto_recovery_repeat_block",
})


def full_access_enabled(agent) -> bool:
    """Use the same live session identity as the approval gate, including revocation."""
    from tools import approval
    key = approval.get_current_session_key(default="") or agent.session_id or ""
    return approval._YOLO_MODE_FROZEN or approval.is_session_yolo_enabled(key)


def set_tool_guardrail_halt(agent, decision) -> str:
    """Return guidance when the loop can be redirected; otherwise record the halt."""
    if not decision.should_halt or agent._tool_guardrail_halt_decision is not None:
        return ""
    interrupted = getattr(agent, "_interrupt_requested", False)
    hard_interrupt = getattr(agent, "_hard_interrupt_requested", None)
    budget = getattr(agent, "iteration_budget", None)
    can_redirect = (
        decision.code in RECOVERABLE_LOOP_CODES and not interrupted
        and not (hard_interrupt is not None and hard_interrupt.is_set())
        and (budget is None or budget.remaining > 0) and full_access_enabled(agent)
    )
    count = agent._tool_guardrails.recover_from_halt(decision, MAX_STRATEGY_RECOVERIES) if can_redirect else 0
    if count:
        record_guardrail_decision(agent, decision.action, decision.code)
        agent._emit_diagnostic_status(f"Меняю подход · {count}/{MAX_STRATEGY_RECOVERIES}")
        logger.info("Tool loop recovery %s/%s: %s (%s)", count, MAX_STRATEGY_RECOVERIES,
                    decision.tool_name, decision.code)
        return (
            f"\n\n[Freedom automatic continuation {count}/{MAX_STRATEGY_RECOVERIES}: "
            f"{decision.message} Full access is enabled. Continue the original user task now; "
            "do not ask the user to type continue. This is a strategy change, not permission "
            "to repeat the blocked operation. Inspect the actual error and any effects that "
            "already landed. Choose a materially different method: repair the code or inputs, "
            "use the documented tool API, a simpler command, or another available tool. "
            "Do not run the same probe again or reset the loop detector. Earlier calls may "
            "already have effects. Preserve all permission, payment, authentication and safety gates. "
            "If progress requires missing credentials or a human action, explain that exact "
            "blocker. Verify the result before claiming success.]"
        )
    agent._tool_guardrail_halt_decision = decision
    record_guardrail_decision(agent, decision.action, decision.code)
    return ""


def toolguard_controlled_halt_response(agent, decision) -> str:
    """A bounded recovery failure ends honestly, without another continue demand."""
    recovered = agent._tool_guardrails.recovery_count
    if recovered and decision.code in RECOVERABLE_LOOP_CODES and full_access_enabled(agent):
        return (
            f"Автоматическое продолжение использовано {recovered} раз, "
            "но снова обнаружен повтор без продвижения. Задача не завершена. "
            f"Проблемный инструмент: {decision.tool_name or 'неизвестен'}. "
            "Остановил повторение, чтобы не зациклиться; подробности — в последнем результате инструмента."
        )
    return (
        f"I stopped retrying because I kept running {decision.tool_name or 'the same tool'} "
        f"{decision.count} times without making progress. The last result above shows what "
        "blocked it. Tell me how you'd like to proceed, or send `continue` and I'll try a "
        "different approach."
    )


def append_guardrail_observation(agent, tool_name, function_args, function_result, *, failed, tool_call_id=""):
    decision = agent._tool_guardrails.after_call(tool_name, function_args, function_result, failed=failed)
    stall_notice = result_stub = stall_kind = None
    if agent._stall_guards_enabled():
        try:
            observation = agent._tool_guardrails.observe_call(
                tool_name, function_args, function_result if isinstance(function_result, str) else None,
                tool_call_id=tool_call_id, failed=failed,
            )
            stall_notice, result_stub, stall_kind = observation.notice, observation.stub, observation.kind
        except Exception as exc:
            logger.debug("stall-guard identical-call observation failed: %s", exc)
    if result_stub and isinstance(function_result, str):
        function_result = result_stub
    record_guardrail_warnings(agent, decision, stall_kind if stall_notice else None)
    halt = decision if decision.should_halt else agent._tool_guardrails.halt_decision
    if halt is not None and halt.should_halt:
        recovery_notice = set_tool_guardrail_halt(agent, halt)
        function_result = (function_result or "") + recovery_notice if recovery_notice else append_toolguard_guidance(function_result, halt)
    elif decision.action == "warn":
        function_result = append_toolguard_guidance(function_result, decision)
    if stall_notice:
        function_result = (function_result or "") + "\n\n" + stall_notice
    return function_result


def guardrail_block_result(agent, decision) -> str:
    notice = set_tool_guardrail_halt(agent, decision)
    return toolguard_synthetic_result(decision) + "\n[This call was blocked before execution.]" + notice
