"""LLM provider adapters cho Gemini, OpenAI và chế độ Mock offline."""

import json
import os
import re
import sys
import time
from typing import Any, Dict, List

from dotenv import load_dotenv


if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()


class BaseLLMProvider:
    """Giao diện chung cho các LLM provider."""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Giả lập quyết định Tool Calling để kiểm thử không tốn API."""

    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if re.search(r"\bMB\d+\b", prompt, re.IGNORECASE):
            return (
                "Tôi là Chatbot Baseline nên không thể tra cứu hồ sơ "
                "hội viên hoặc đặt lịch tập."
            )
        return (
            "Người mới có thể bắt đầu với 2–3 buổi tập mỗi tuần, "
            "tăng dần cường độ và dành thời gian phục hồi phù hợp."
        )

    @staticmethod
    def _split_prompt(prompt: str):
        marker = "\n\nKẾT QUẢ CÔNG CỤ ĐÃ NHẬN:\n"
        if marker not in prompt:
            return prompt, []

        user_part, raw_observations = prompt.split(marker, 1)
        try:
            return user_part, json.loads(raw_observations)
        except json.JSONDecodeError:
            return user_part, []

    @staticmethod
    def _extract_datetime(text: str):
        match = re.search(
            r"([0-2]\d:[0-5]\d).*?(\d{2}/\d{2}/\d{4})",
            text,
            re.DOTALL,
        )
        return f"{match.group(1)} {match.group(2)}" if match else None

    @staticmethod
    def _extract_trainer(text: str):
        match = re.search(
            r"(HLV\s+.+?)(?=\s+(?:vào|lúc)\b|[,.]|$)",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        user_text, observations = self._split_prompt(prompt)
        user_lower = user_text.lower()

        member_match = re.search(r"\bMB\d+\b", user_text, re.IGNORECASE)
        member_id = member_match.group(0).upper() if member_match else None
        datetime_str = self._extract_datetime(user_text)
        explicit_trainer = self._extract_trainer(user_text)
        wants_booking = any(
            phrase in user_lower for phrase in ("đặt lịch", "booking", "schedule")
        )

        if observations:
            latest = observations[-1]
            result = latest.get("result", {})
            status = result.get("status")
            tool_name = latest.get("tool_name")

            if status != "SUCCESS":
                return {
                    "type": "text",
                    "content": result.get(
                        "message", result.get("error", "Công cụ xử lý không thành công.")
                    ),
                    "thought": "Kết quả công cụ không thành công nên dừng xử lý.",
                }

            if tool_name == "schedule_training_session":
                return {
                    "type": "text",
                    "content": result.get("message", "Đã hoàn thành việc đặt lịch tập."),
                    "thought": "Đã có kết quả đặt lịch để trả lời người dùng.",
                }

            if tool_name == "health_profile_query" and wants_booking:
                if not datetime_str:
                    return {
                        "type": "text",
                        "content": "Bạn cần cung cấp thời gian muốn đặt buổi tập.",
                        "thought": "Yêu cầu đặt lịch còn thiếu thời gian.",
                    }

                trainer_name = result.get("data", {}).get("trainer")
                return {
                    "type": "tool_call",
                    "tool_name": "schedule_training_session",
                    "arguments": {
                        "member_id": member_id,
                        "datetime_str": datetime_str,
                        "trainer_name": trainer_name,
                    },
                    "thought": "Đã biết huấn luyện viên nên có thể đặt lịch.",
                }

            if tool_name == "health_profile_query":
                data = result.get("data", {})
                return {
                    "type": "text",
                    "content": (
                        f"Hội viên {result.get('member_id', member_id)} "
                        f"({data.get('full_name', '')}) có mục tiêu "
                        f"{data.get('fitness_goal', '')}, trình độ "
                        f"{data.get('fitness_level', '')}, huấn luyện viên "
                        f"{data.get('trainer', '')}."
                    ),
                    "thought": "Đã có đủ dữ liệu hồ sơ để trả lời.",
                }

        if wants_booking:
            if not member_id:
                return {
                    "type": "text",
                    "content": "Bạn cần cung cấp mã hội viên để đặt lịch.",
                    "thought": "Yêu cầu còn thiếu mã hội viên.",
                }
            if not datetime_str:
                return {
                    "type": "text",
                    "content": "Bạn cần cung cấp thời gian muốn đặt buổi tập.",
                    "thought": "Yêu cầu còn thiếu thời gian.",
                }
            if explicit_trainer:
                return {
                    "type": "tool_call",
                    "tool_name": "schedule_training_session",
                    "arguments": {
                        "member_id": member_id,
                        "datetime_str": datetime_str,
                        "trainer_name": explicit_trainer,
                    },
                    "thought": "Đã có đủ thông tin để đặt lịch tập.",
                }
            return {
                "type": "tool_call",
                "tool_name": "health_profile_query",
                "arguments": {"member_id": member_id},
                "thought": "Cần tra cứu huấn luyện viên trước khi đặt lịch.",
            }

        lookup_keywords = (
            "tra cứu",
            "hồ sơ",
            "thông tin",
            "kiểm tra",
            "mục tiêu",
            "huấn luyện viên",
        )
        if member_id and any(keyword in user_lower for keyword in lookup_keywords):
            return {
                "type": "tool_call",
                "tool_name": "health_profile_query",
                "arguments": {"member_id": member_id},
                "thought": f"Cần tra cứu hồ sơ hội viên {member_id}.",
            }

        return {
            "type": "text",
            "content": (
                "Người mới có thể bắt đầu với 2–3 buổi tập mỗi tuần, "
                "tăng dần cường độ và dành thời gian phục hồi phù hợp."
            ),
            "thought": "Đây là câu hỏi chung nên không cần gọi công cụ.",
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini với Native Tool Calling."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return MockOfflineProvider().generate(prompt, system_prompt)
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            return response.text or ""
        except Exception as error:
            return f"[Gemini Exception]: {error}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return MockOfflineProvider().generate_with_tools(
                prompt, tools_schema, system_prompt
            )

        for attempt in range(3):
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                declarations = [
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                    for tool in tools_schema
                    if tool.get("name") and tool.get("parameters")
                ]
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt or None,
                    tools=[{"function_declarations": declarations}] if declarations else None,
                    temperature=0.2,
                )
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )

                if response.function_calls:
                    call = response.function_calls[0]
                    arguments = dict(call.args) if call.args else {}
                    return {
                        "type": "tool_call",
                        "tool_name": call.name,
                        "arguments": arguments,
                        "thought": f"Gemini chọn công cụ {call.name}.",
                    }

                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini trả lời trực tiếp.",
                }
            except Exception as error:
                error_str = str(error)
                delay_match = re.search(r"retry in ([\d.]+)", error_str)
                delay = float(delay_match.group(1)) if delay_match else 0
                if ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str) and attempt < 2 and 0 < delay <= 12:
                    wait_time = int(delay) + 1
                    print(f"[Gemini API Warning] Rate limit 429 RPM, đang chờ {wait_time} giây rồi thử lại...")
                    time.sleep(wait_time)
                    continue
                print(f"[Gemini API Warning] Chuyển sang Mock: {error}")
                return MockOfflineProvider().generate_with_tools(
                    prompt, tools_schema, system_prompt
                )


class OpenAIProvider(BaseLLMProvider):
    """OpenAI với Native Tool Calling."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return MockOfflineProvider().generate(prompt, system_prompt)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as error:
            return f"[OpenAI Exception]: {error}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return MockOfflineProvider().generate_with_tools(
                prompt, tools_schema, system_prompt
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                }
                for tool in tools_schema
                if tool.get("name")
            ]
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )

            message = response.choices[0].message
            if message.tool_calls:
                call = message.tool_calls[0]
                arguments = (
                    json.loads(call.function.arguments)
                    if call.function.arguments
                    else {}
                )
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": arguments,
                    "thought": f"OpenAI chọn công cụ {call.function.name}.",
                }

            return {
                "type": "text",
                "content": message.content or "",
                "thought": "OpenAI trả lời trực tiếp.",
            }
        except Exception as error:
            print(f"[OpenAI API Warning] Chuyển sang Mock: {error}")
            return MockOfflineProvider().generate_with_tools(
                prompt, tools_schema, system_prompt
            )


def get_llm_provider() -> BaseLLMProvider:
    """Tạo provider theo biến LLM_PROVIDER trong .env."""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        return (
            GeminiProvider()
            if key and key != "your_gemini_api_key_here"
            else MockOfflineProvider()
        )
    if provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        return (
            OpenAIProvider()
            if key and key != "your_openai_api_key_here"
            else MockOfflineProvider()
        )
    return MockOfflineProvider()
