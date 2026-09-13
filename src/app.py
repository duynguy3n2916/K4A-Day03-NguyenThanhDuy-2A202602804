"""Ứng dụng so sánh Chatbot và Health Coach ReAct Agent."""

import json
import os
import sys
import time

from dotenv import load_dotenv


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_server import MCPHealthCoachServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    MAX_ITERATIONS,
    REACT_AGENT_SYSTEM_PROMPT,
)
from providers import MockOfflineProvider, get_llm_provider
from tools import BOOKINGS


load_dotenv()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_test_cases():
    """Đọc bộ test của chủ đề Health Coach."""
    config_path = os.path.join(BASE_DIR, "config", "test_cases.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(BASE_DIR, "config", "test_cases.example.json")
        print("Chưa có test_cases.json; đang dùng file ví dụ.")

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_waterfall_trace(trace_data: list):
    """Ghi toàn bộ sự kiện Agent vào file JSON."""
    trace_path = os.path.join(BASE_DIR, "docs", "trace_waterfall.json")
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    with open(trace_path, "w", encoding="utf-8") as file:
        json.dump(trace_data, file, ensure_ascii=False, indent=2)
    print(f"Đã lưu {len(trace_data)} sự kiện tại {trace_path}")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot không được cung cấp Tool."""
    print(f"\n[CHATBOT BASELINE] {user_query}")
    response = provider.generate(
        user_query,
        system_prompt=CHATBOT_BASELINE_PROMPT,
    )
    print(f"[ANSWER] {response}")
    return response


def build_agent_prompt(user_query: str, observations: list) -> str:
    """Ghép yêu cầu ban đầu với các Observation của vòng trước."""
    prompt = f"YÊU CẦU NGƯỜI DÙNG:\n{user_query}"
    if observations:
        prompt += (
            "\n\nKẾT QUẢ CÔNG CỤ ĐÃ NHẬN:\n"
            + json.dumps(observations, ensure_ascii=False, indent=2)
        )
    return prompt


def run_react_agent(
    user_query: str,
    provider,
    mcp_server: MCPHealthCoachServer,
) -> list:
    """Chạy vòng lặp LLM -> Action -> Observation -> LLM."""
    print(f"\n[REACT AGENT] {user_query}")

    trace_logs = []
    observations = []
    tools_list = mcp_server.list_tools()

    for step in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- ReAct Step {step}/{MAX_ITERATIONS} ---")
        agent_prompt = build_agent_prompt(user_query, observations)

        llm_start = time.perf_counter()
        llm_response = provider.generate_with_tools(
            agent_prompt,
            tools_list,
            system_prompt=REACT_AGENT_SYSTEM_PROMPT,
        )
        llm_latency_ms = round((time.perf_counter() - llm_start) * 1000, 2)

        response_type = llm_response.get("type")
        thought = llm_response.get(
            "thought", "Đang xác định hành động tiếp theo."
        )
        print(f"[THOUGHT] {thought}")

        if response_type == "text":
            final_content = llm_response.get("content", "")
            print(f"[FINAL ANSWER] {final_content}")
            trace_logs.append(
                {
                    "step": step,
                    "query": user_query,
                    "action_type": "FINAL_ANSWER",
                    "thought": thought,
                    "output": final_content,
                    "llm_latency_ms": llm_latency_ms,
                }
            )
            return trace_logs

        if response_type == "tool_call":
            tool_name = llm_response.get("tool_name", "")
            arguments = llm_response.get("arguments", {})
            print(f"[ACTION] {tool_name}({arguments})")

            tool_start = time.perf_counter()
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            tool_latency_ms = round((time.perf_counter() - tool_start) * 1000, 2)
            observation = mcp_result.get("result", {})
            print(
                "[OBSERVATION] "
                + json.dumps(observation, ensure_ascii=False)
            )

            trace_logs.append(
                {
                    "step": step,
                    "query": user_query,
                    "action_type": "TOOL_EXECUTION",
                    "thought": thought,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "observation": observation,
                    "llm_latency_ms": llm_latency_ms,
                    "tool_latency_ms": tool_latency_ms,
                }
            )
            observations.append(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": observation,
                }
            )
            continue

        error_message = "Provider trả về kiểu phản hồi không hợp lệ."
        print(f"[ERROR] {error_message}")
        trace_logs.append(
            {
                "step": step,
                "query": user_query,
                "action_type": "ERROR",
                "output": error_message,
            }
        )
        return trace_logs

    final_message = (
        f"Agent chưa hoàn thành yêu cầu sau {MAX_ITERATIONS} bước."
    )
    print(f"[FINAL ANSWER] {final_message}")
    trace_logs.append(
        {
            "step": MAX_ITERATIONS + 1,
            "query": user_query,
            "action_type": "MAX_ITERATIONS_REACHED",
            "output": final_message,
        }
    )
    return trace_logs


def evaluate_trace(test_case: dict, logs: list):
    """So sánh Tool sequence và trạng thái thực tế với kỳ vọng."""
    actual_tools = [
        event["tool_name"]
        for event in logs
        if event.get("action_type") == "TOOL_EXECUTION"
    ]
    actual_statuses = [
        event.get("observation", {}).get("status")
        for event in logs
        if event.get("action_type") == "TOOL_EXECUTION"
    ]
    expected_tools = test_case.get("expected_tool_sequence", [])
    expected_statuses = test_case.get("expected_status_sequence", [])
    has_final_answer = any(
        event.get("action_type") == "FINAL_ANSWER" for event in logs
    )

    errors = []
    if actual_tools != expected_tools:
        errors.append(
            f"Tool sequence: mong đợi {expected_tools}, thực tế {actual_tools}"
        )
    if expected_statuses and actual_statuses != expected_statuses:
        errors.append(
            f"Status sequence: mong đợi {expected_statuses}, "
            f"thực tế {actual_statuses}"
        )
    if not has_final_answer:
        errors.append("Không có FINAL_ANSWER")

    return not errors, errors


def run_test_suite(provider, mcp_server, tests):
    """Chạy và chấm PASS/FAIL toàn bộ test case."""
    print("\n[TEST SUITE] Health Coach Agent")
    all_traces = []
    passed_count = 0
    BOOKINGS.clear()

    for test_case in tests:
        print("\n" + "=" * 58)
        print(
            f"[{test_case['id']}] {test_case['type']} - "
            f"{test_case['complexity']}"
        )
        print(f"Kỳ vọng: {test_case['expected_behavior']}")

        logs = run_react_agent(
            test_case["question"],
            provider,
            mcp_server,
        )
        passed, errors = evaluate_trace(test_case, logs)
        for event in logs:
            event["test_id"] = test_case["id"]
            event["test_passed"] = passed
        all_traces.extend(logs)

        if passed:
            passed_count += 1
            print(f"[PASS] {test_case['id']}")
        else:
            print(f"[FAIL] {test_case['id']}")
            for error in errors:
                print(f"  - {error}")

        time.sleep(1)

    print("\n" + "=" * 58)
    print(f"KẾT QUẢ: {passed_count}/{len(tests)} test PASS")
    if all_traces:
        save_waterfall_trace(all_traces)
    return passed_count == len(tests)


def main():
    print("=" * 58)
    print("DAY 03 LAB - HEALTH COACH REACT AGENT")
    print("=" * 58)

    provider = (
        MockOfflineProvider()
        if "--mock" in sys.argv
        else get_llm_provider()
    )
    mcp_server = MCPHealthCoachServer()
    tests = load_test_cases()

    print(f"LLM Provider: {provider.__class__.__name__}")
    print(f"MCP Server: {mcp_server.server_name}")
    print(f"Đã tải {len(tests)} test cases.")

    if "--interactive" in sys.argv:
        print("\n[INTERACTIVE MODE]")
        print("Gõ 'exit' hoặc 'quit' để thoát.")
        session_traces = []
        while True:
            try:
                user_input = input("\nBạn hỏi: ").strip()
                if not user_input or user_input.lower() in {"exit", "quit"}:
                    print("Đã kết thúc phiên.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                session_traces.extend(logs)
                save_waterfall_trace(session_traces)
            except (KeyboardInterrupt, EOFError):
                print("\nĐã kết thúc phiên.")
                break
        return

    if "--all" in sys.argv:
        success = run_test_suite(provider, mcp_server, tests)
        raise SystemExit(0 if success else 1)

    if "--compare" in sys.argv:
        sample_query = tests[1]["question"]
        run_baseline_chatbot(sample_query, provider)
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        return

    print("\nCách sử dụng:")
    print("  python src/app.py --all --mock")
    print("  python src/app.py --interactive --mock")
    print("  python src/app.py --compare --mock")
    print("  python src/app.py --all       # dùng provider trong .env")
    print("\nĐang chạy demo TC02...")
    logs = run_react_agent(tests[1]["question"], provider, mcp_server)
    save_waterfall_trace(logs)


if __name__ == "__main__":
    main()
