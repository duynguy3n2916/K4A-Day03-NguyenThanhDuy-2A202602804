# BÁO CÁO NGHIỆM THU BÀI LAB 3

> **Họ và tên:** Nguyễn Thành Duy
>
> **Mã học viên:** 2A202602804
>
> **Chủ đề:** Trợ lý Huấn luyện Sức khỏe Cá nhân

## 1. Agentic Fit Scoring Matrix

| Tiêu chí | Điểm | Giải trình |
| :--- | :---: | :--- |
| Multi-step Reasoning | 4/5 | Agent phải tra cứu hồ sơ để biết huấn luyện viên trước khi đặt lịch. |
| Tool Interaction | 5/5 | Hệ thống dùng một Tool tra cứu và một Tool tạo lịch tập. |
| Dynamic Decision | 4/5 | Kết quả tra cứu quyết định việc đặt lịch hay dừng khi không tìm thấy hội viên. |
| Long Horizon Goal | 3/5 | Hệ thống có thể mở rộng để theo dõi mục tiêu qua nhiều buổi, còn bài lab mô phỏng một phiên xử lý. |
| **Tổng** | **16/20** | Bài toán phù hợp với Agentic System. |

## 2. Tool và luồng ReAct

Hai Tool được công bố qua MCP Server:

- `health_profile_query(member_id)`: tra cứu hồ sơ luyện tập.
- `schedule_training_session(member_id, datetime_str, trainer_name)`: đặt lịch tập.

Luồng nhiều bước TC04:

```text
Yêu cầu đặt lịch nhưng chưa biết huấn luyện viên
→ health_profile_query(MB002)
→ Observation: trainer = HLV Nguyễn Thu Hà
→ schedule_training_session(MB002, 19:00 22/09/2026, HLV Nguyễn Thu Hà)
→ Final Answer
```

## 3. Trích Waterfall Trace tiêu biểu

Đoạn sau được trích xuất trực tiếp khi chạy bộ kiểm thử với **Google Gemini API thật (`GeminiProvider`)**, thể hiện đầy đủ độ trễ thực thi (`llm_latency_ms`, `tool_latency_ms`) và tiến trình suy luận đa bước (Thought $\rightarrow$ Action $\rightarrow$ Observation $\rightarrow$ Final Answer) cho ca kiểm thử phức tạp **TC04**:

```json
[
  {
    "step": 1,
    "query": "Kiểm tra huấn luyện viên phụ trách MB002 rồi đặt lịch tập với người đó vào lúc 19:00 ngày 22/09/2026.",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini chọn công cụ health_profile_query.",
    "tool_name": "health_profile_query",
    "arguments": {
      "member_id": "MB002"
    },
    "observation": {
      "status": "SUCCESS",
      "member_id": "MB002",
      "data": {
        "full_name": "Lê Hoàng Nam",
        "age": 28,
        "fitness_goal": "Tăng cơ",
        "current_weight_kg": 65,
        "target_weight_kg": 72,
        "fitness_level": "Trung bình",
        "trainer": "HLV Nguyễn Thu Hà",
        "status": "Đang hoạt động"
      }
    },
    "llm_latency_ms": 2616.27,
    "tool_latency_ms": 0.15,
    "test_id": "TC04",
    "test_passed": true
  },
  {
    "step": 2,
    "query": "Kiểm tra huấn luyện viên phụ trách MB002 rồi đặt lịch tập với người đó vào lúc 19:00 ngày 22/09/2026.",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini chọn công cụ schedule_training_session.",
    "tool_name": "schedule_training_session",
    "arguments": {
      "member_id": "MB002",
      "datetime_str": "19:00 22/09/2026",
      "trainer_name": "HLV Nguyễn Thu Hà"
    },
    "observation": {
      "status": "SUCCESS",
      "booking_id": "FIT-MB002-002",
      "member_id": "MB002",
      "datetime": "19:00 22/09/2026",
      "trainer": "HLV Nguyễn Thu Hà",
      "message": "Đã đặt lịch tập cho hội viên MB002 với HLV Nguyễn Thu Hà vào lúc 19:00 22/09/2026."
    },
    "llm_latency_ms": 2320.18,
    "tool_latency_ms": 0.11,
    "test_id": "TC04",
    "test_passed": true
  },
  {
    "step": 3,
    "query": "Kiểm tra huấn luyện viên phụ trách MB002 rồi đặt lịch tập với người đó vào lúc 19:00 ngày 22/09/2026.",
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini trả lời trực tiếp.",
    "output": "Đã kiểm tra thông tin cho hội viên **Lê Hoàng Nam (MB002)**. Huấn luyện viên phụ trách của bạn là **HLV Nguyễn Thu Hà**.\n\nTôi đã đặt lịch tập thành công cho bạn với chi tiết như sau:\n- **Mã đặt lịch:** FIT-MB002-002\n- **Thời gian:** 19:00 ngày 22/09/2026\n- **Huấn luyện viên:** HLV Nguyễn Thu Hà\n\nChúc bạn có buổi tập luyện hiệu quả để sớm đạt mục tiêu tăng cơ!",
    "llm_latency_ms": 3055.86,
    "test_id": "TC04",
    "test_passed": true
  }
]
```

Toàn bộ vết thực thi của cả 5 test cases được lưu tại: [`docs/trace_waterfall.json`](trace_waterfall.json).

## 4. Kết quả kiểm thử

### A. Kiểm thử với Live LLM API (Google Gemini)

Lệnh thực thi:

```powershell
python src/app.py --all
```

| Test | Nội dung | Tool sequence kỳ vọng | Trạng thái thực tế | Độ trễ LLM trung bình | Kết quả |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **TC01** | Câu hỏi luyện tập chung | Không gọi Tool | Không gọi Tool | 4,513 ms | **PASS** |
| **TC02** | Tra cứu MB001 | `health_profile_query` | `health_profile_query` [SUCCESS] | 2,095 ms | **PASS** |
| **TC03** | Đặt lịch đủ dữ liệu | `schedule_training_session` | `schedule_training_session` [SUCCESS] | 2,484 ms | **PASS** |
| **TC04** | Tra cứu rồi đặt lịch | `health_profile_query → schedule_training_session` | `query → schedule` [SUCCESS, SUCCESS] | 2,664 ms | **PASS** |
| **TC05** | Hội viên không tồn tại | `health_profile_query → NOT_FOUND` | `health_profile_query` [NOT_FOUND] | 1,895 ms | **PASS** |

**Kết quả nghiệm thu Live API:** **5/5 test PASS (100%)**, không gặp lỗi hoặc fallback sang Mock.

### B. Kiểm thử Offline (Mock Offline Provider)

Lệnh thực thi:

```powershell
python src/app.py --all --mock
```

**Kết quả Offline:** **5/5 test PASS (100%)**.

## 5. Nghiệm thu API thật và nộp bài

- [x] File log `docs/trace_waterfall.json` được tạo thành công với đầy đủ các bước thực thi từ LLM API thật.
- [x] Đã hoàn thiện Tool Schema, backend, MCP Server và ReAct Loop.
- [x] Chạy 5/5 test thành công bằng LLM API thật (`python src/app.py --all`).
- [x] Chạy 5/5 test thành công bằng Mock Offline (`python src/app.py --all --mock`).
- [x] Đã thử nghiệm chế độ đàm thoại trực tiếp (`python src/app.py --interactive`).
- [x] Đã hoàn thiện toàn bộ biên bản kiểm thử trong `docs/trace_eval.md`.
- [x] Sẵn sàng commit, push GitHub và nộp liên kết lên VLearn.
