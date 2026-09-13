"""MCP Server mô phỏng cho Health Coach Agent."""

import json
import sys
from typing import Any, Dict, List

from tools import TOOLS_SCHEMA, dispatch_tool_call


if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class MCPHealthCoachServer:
    """Công bố và điều phối các Tool của trợ lý huấn luyện sức khỏe."""

    def __init__(self, server_name: str = "personal-health-coach-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả danh sách Tool Schema cho LLM."""
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi Tool và đóng gói kết quả theo JSON-RPC 2.0."""
        raw_result = dispatch_tool_call(tool_name, arguments)
        try:
            content = json.loads(raw_result)
        except json.JSONDecodeError:
            content = {
                "status": "ERROR",
                "message": "Tool trả về dữ liệu JSON không hợp lệ.",
                "raw": raw_result,
            }

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content,
        }


if __name__ == "__main__":
    server = MCPHealthCoachServer()
    tools = server.list_tools()

    print("=" * 58)
    print("KIỂM THỬ MCP SERVER - PERSONAL HEALTH COACH")
    print("=" * 58)
    print(
        f"Khởi tạo thành công {server.server_name} "
        f"(Version: {server.version})"
    )
    print(f"Số lượng Tools công bố: {len(tools)}")
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")

    samples = [
        ("health_profile_query", {"member_id": "MB001"}),
        (
            "schedule_training_session",
            {
                "member_id": "MB001",
                "datetime_str": "18:00 20/09/2026",
                "trainer_name": "HLV Trần Quốc Bảo",
            },
        ),
    ]
    for tool_name, arguments in samples:
        print(f"\nKiểm tra {tool_name}:")
        print(
            json.dumps(
                server.call_tool(tool_name, arguments),
                ensure_ascii=False,
                indent=2,
            )
        )
