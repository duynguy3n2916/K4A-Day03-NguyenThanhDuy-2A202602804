"""Tool schemas và lớp thực thi cho Health Coach Agent."""

import json
from typing import Any, Dict


TOOLS_SCHEMA = [
    {
        "name": "health_profile_query",
        "description": (
            "Tra cứu hồ sơ, mục tiêu luyện tập và huấn luyện viên "
            "phụ trách của hội viên bằng mã hội viên."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "Mã hội viên cần tra cứu, ví dụ: MB001",
                }
            },
            "required": ["member_id"],
        },
    },
    {
        "name": "schedule_training_session",
        "description": "Đặt lịch tập cho hội viên với huấn luyện viên phụ trách.",
        "parameters": {
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "Mã hội viên cần đặt lịch, ví dụ: MB001",
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian buổi tập, ví dụ: 18:00 20/09/2026",
                },
                "trainer_name": {
                    "type": "string",
                    "description": "Tên huấn luyện viên phụ trách (ví dụ: HLV Trần Quốc Bảo)",
                },
            },
            "required": ["member_id", "datetime_str", "trainer_name"],
        },
    },
]


MOCK_DATABASE = {
    "MB001": {
        "full_name": "Nguyễn Minh Anh",
        "age": 24,
        "fitness_goal": "Giảm cân",
        "current_weight_kg": 68,
        "target_weight_kg": 60,
        "fitness_level": "Cơ bản",
        "trainer": "HLV Trần Quốc Bảo",
        "status": "Đang hoạt động",
    },
    "MB002": {
        "full_name": "Lê Hoàng Nam",
        "age": 28,
        "fitness_goal": "Tăng cơ",
        "current_weight_kg": 65,
        "target_weight_kg": 72,
        "fitness_level": "Trung bình",
        "trainer": "HLV Nguyễn Thu Hà",
        "status": "Đang hoạt động",
    },
}

# Lịch chỉ tồn tại trong bộ nhớ của lần chạy hiện tại.
BOOKINGS = []


def execute_health_profile_query(member_id: str) -> str:
    """Tra cứu hồ sơ luyện tập theo mã hội viên."""
    normalized_id = member_id.strip().upper()
    member = MOCK_DATABASE.get(normalized_id)

    if member:
        return json.dumps(
            {"status": "SUCCESS", "member_id": normalized_id, "data": member},
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy hội viên có mã '{normalized_id}'.",
        },
        ensure_ascii=False,
    )


def _normalize_trainer(name: str) -> str:
    """Loại bỏ tiền tố chức danh (HLV) để so sánh tên linh hoạt."""
    cleaned = name.strip()
    if cleaned.lower().startswith("hlv"):
        cleaned = cleaned[3:].strip(". ")
    return cleaned.strip().casefold()


def execute_schedule_training_session(
    member_id: str, datetime_str: str, trainer_name: str
) -> str:
    """Kiểm tra dữ liệu và đặt lịch tập cho hội viên."""
    normalized_id = member_id.strip().upper()
    member = MOCK_DATABASE.get(normalized_id)

    if not member:
        return json.dumps(
            {
                "status": "NOT_FOUND",
                "message": f"Không tìm thấy hội viên có mã '{normalized_id}'.",
            },
            ensure_ascii=False,
        )

    assigned_trainer = member["trainer"]
    if _normalize_trainer(trainer_name) != _normalize_trainer(assigned_trainer):
        return json.dumps(
            {
                "status": "INVALID_TRAINER",
                "message": (
                    f"Huấn luyện viên phụ trách hội viên {normalized_id} là "
                    f"{assigned_trainer}, không phải {trainer_name}."
                ),
            },
            ensure_ascii=False,
        )

    booking = {
        "booking_id": f"FIT-{normalized_id}-{len(BOOKINGS) + 1:03d}",
        "member_id": normalized_id,
        "datetime": datetime_str.strip(),
        "trainer": assigned_trainer,
    }
    BOOKINGS.append(booking)

    return json.dumps(
        {
            "status": "SUCCESS",
            **booking,
            "message": (
                f"Đã đặt lịch tập cho hội viên {normalized_id} với "
                f"{assigned_trainer} vào lúc {datetime_str.strip()}."
            ),
        },
        ensure_ascii=False,
    )


TOOL_ROUTER = {
    "health_profile_query": execute_health_profile_query,
    "schedule_training_session": execute_schedule_training_session,
}


def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Tìm và thực thi Tool theo tên."""
    tool = TOOL_ROUTER.get(tool_name)
    if not tool:
        return json.dumps(
            {"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại."},
            ensure_ascii=False,
        )

    try:
        return tool(**arguments)
    except (TypeError, ValueError) as error:
        return json.dumps(
            {"status": "EXECUTION_ERROR", "error": str(error)},
            ensure_ascii=False,
        )
