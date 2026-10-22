# -*- coding: utf-8 -*-
"""
Benchmark trích xuất Knowledge Graph pháp luật giao thông qua 9router.

Cách chạy:
    python gemini_extractor_benchmark-v4.py

Biến môi trường tuỳ chọn:
    NINEROUTER_BASE_URL  (mặc định http://localhost:20128/v1)
    NINEROUTER_API_KEY
    MODEL_NAME           (mặc định ag/gemini-3.8-flash-high)
    ONTOLOGY_FILE        (mặc định ontology_v9.json)
    REQUEST_TIMEOUT      giây, mặc định 300
    MAX_RETRIES          mặc định 0 (benchmark không nên retry)
    TEMPERATURE          mặc định 0.1
    OUTPUT_FILE          mặc định out.txt (cạnh script)
    PRINT_JSON=1         in toàn bộ JSON ra terminal (mặc định chỉ ghi file)
"""

import json
import os
import re
import sys
import time
from typing import List, Optional

# ==========================================
# 0. ÉP UTF-8 CHO CONSOLE WINDOWS
# ==========================================
# Windows mặc định dùng cp1252/cp437 -> không in được emoji và tiếng Việt.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ==========================================
# 1. KIỂM TRA THƯ VIỆN (BÁO LỖI ĐÚNG BẢN PYTHON)
# ==========================================
try:
    import openai
    from openai import OpenAI
    from pydantic import BaseModel, Field, ValidationError
except ImportError as exc:
    print(
        f"❌ Không import được thư viện: {exc}\n"
        f"   Python đang dùng : {sys.executable}\n"
        f"   Cài bằng         : \"{sys.executable}\" -m pip install -U openai pydantic"
    )
    raise SystemExit(2)

# ==========================================
# 2. CẤU HÌNH
# ==========================================
ONTOLOGY_FILE = os.getenv("ONTOLOGY_FILE", "ontology_v9.json")

BASE_URL = os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
API_KEY = os.getenv("NINEROUTER_API_KEY", "sk-3453de06c19c72e7-6e7f89-88f210da")
MODEL_NAME = os.getenv("MODEL_NAME", "ag/gemini-3.8-flash-high")

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "0"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

# Kết quả JSON ghi ra file (mặc định out.txt cạnh script).
OUTPUT_FILE = os.getenv(
    "OUTPUT_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out.txt"),
)
# Đặt PRINT_JSON=1 nếu vẫn muốn in toàn bộ JSON ra terminal.
PRINT_JSON = os.getenv("PRINT_JSON", "0") == "1"

# ==========================================
# 3. ĐỌC TỰ ĐỘNG ONTOLOGY_V9.JSON
# ==========================================

def load_ontology(file_path: str):
    """
    Đọc file ontology.json để lấy danh sách Lớp (Classes) và Quan hệ (Relationships).
    """
    if not os.path.exists(file_path):
        # Tìm trong cùng thư mục script nếu chạy từ vị trí khác
        alt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            raise FileNotFoundError(f"❌ Không tìm thấy file Ontology tại: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    classes_info = data.get("classes", [])
    relations_info = data.get("relationships", [])

    if not classes_info:
        raise ValueError("Ontology không có mục 'classes' hoặc danh sách rỗng.")
    if not relations_info:
        raise ValueError("Ontology không có mục 'relationships' hoặc danh sách rỗng.")

    valid_classes = [c["id"] for c in classes_info]
    valid_relations = [r["relation"] for r in relations_info]

    # System prompt: đưa TOÀN BỘ ontology + một ví dụ JSON mẫu (few-shot).
    # Không gửi schema cho model, model tự sinh JSON theo hướng dẫn này.
    system_prompt = f"""Bạn là chuyên gia trích xuất Đồ thị Tri thức Pháp luật Giao thông Đường bộ Việt Nam.
Nhiệm vụ của bạn là đọc đoạn văn bản luật và trích xuất thành cấu trúc JSON gồm "nodes" và "relationships" tuân thủ NGHIÊM NGẶT bộ khung Ontology v9.0 bên dưới.

--- BỘ KHUNG ONTOLOGY V9.0 ---
{json.dumps(data, ensure_ascii=False, indent=2)}

--- BẮT BUỘC TRẢ VỀ ĐÚNG CẤU TRÚC JSON MẪU DƯỚI ĐÂY ---
{{
  "nodes": [
    {{
      "id": "hanh_vi_chay_qua_toc_do_10_20",
      "name": "Chạy quá tốc độ quy định từ 10 km/h đến 20 km/h",
      "class_label": "HanhViViPham"
    }},
    {{
      "id": "phuong_tien_o_to",
      "name": "Xe ô tô",
      "class_label": "PhuongTien"
    }},
    {{
      "id": "muc_phat_4m_6m",
      "name": "Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng",
      "class_label": "MucPhatTien"
    }}
  ],
  "relationships": [
    {{
      "source_id": "hanh_vi_chay_qua_toc_do_10_20",
      "relation_type": "AP_DUNG_CHO_PHUONG_TIEN",
      "target_id": "phuong_tien_o_to",
      "description": "Hành vi áp dụng cho loại xe ô tô"
    }},
    {{
      "source_id": "hanh_vi_chay_qua_toc_do_10_20",
      "relation_type": "BI_XU_PHAT_TIEN",
      "target_id": "muc_phat_4m_6m",
      "description": "Khung tiền phạt áp dụng"
    }}
  ]
}}

LƯU Ý QUAN TRỌNG:
1. "class_label" BẮT BUỘC phải nằm trong danh sách "classes" của Ontology.
2. "relation_type" BẮT BUỘC phải nằm trong danh sách "relationships" của Ontology.
3. Không thêm bất kỳ lời giải thích nào ngoài chuỗi JSON.
"""
    return data, valid_classes, valid_relations, system_prompt

# ==========================================
# 4. PYDANTIC SCHEMA — CHỈ DÙNG ĐỂ KIỂM TRA SAU KHI MODEL TRẢ VỀ
#    (KHÔNG gửi schema này cho model, model tự sinh JSON theo prompt)
# ==========================================

class Node(BaseModel):
    id: str = Field(description="ID duy nhất cho thực thể, dạng snake_case")
    name: str = Field(description="Tên hoặc nội dung thực tế của thực thể trong văn bản luật")
    class_label: str = Field(description="Nhãn Class tương ứng thuộc Ontology v9.0")

class Relationship(BaseModel):
    source_id: str = Field(description="ID của nút nguồn (Subject)")
    relation_type: str = Field(description="Loại quan hệ thuộc Ontology v9.0")
    target_id: str = Field(description="ID của nút đích (Object)")
    description: Optional[str] = Field(default="", description="Mô tả ngắn gọn ngữ cảnh")

class KnowledgeGraphExtraction(BaseModel):
    nodes: List[Node] = Field(description="Danh sách các thực thể (Nodes) bóc tách được")
    relationships: List[Relationship] = Field(description="Danh sách các mối quan hệ (Relationships)")

# ==========================================
# 5. VĂN BẢN LUẬT MẪU ĐỂ KIỂM THỬ
# ==========================================

SAMPLE_LAW_TEXT = """
Điều 5. Xử phạt người điều khiển xe ô tô và các loại xe tương tự xe ô tô vi phạm quy tắc giao thông đường bộ
5. Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng đối với người điều khiển xe thực hiện một trong các hành vi vi phạm sau đây:
i) Điều khiển xe chạy quá tốc độ quy định từ 10 km/h đến 20 km/h.
11. Ngoài việc bị phạt tiền, người điều khiển xe thực hiện hành vi vi phạm còn bị áp dụng các hình thức xử phạt bổ sung sau đây:
b) Thực hiện hành vi quy định tại Điểm i Khoản 5 Điều này bị tước quyền sử dụng Giấy phép lái xe từ 01 tháng đến 03 tháng.
12. Để đảm bảo thi hành quyết định xử phạt, người có thẩm quyền có thể áp dụng biện pháp tạm giữ phương tiện đến 07 ngày trước khi ra quyết định xử phạt đối với hành vi điều khiển xe chạy quá tốc độ gây tai nạn giao thông trên đường cao tốc.
"""

# ==========================================
# 6. GỌI 9ROUTER (OPENAI API)
# ==========================================

def _usage_dict(completion) -> dict:
    usage = getattr(completion, "usage", None)
    if not usage:
        return {}
    return {
        "prompt": getattr(usage, "prompt_tokens", 0) or 0,
        "completion": getattr(usage, "completion_tokens", 0) or 0,
        "total": getattr(usage, "total_tokens", 0) or 0,
    }


def _parse_json_loose(text: str) -> dict:
    """Bóc JSON kể cả khi model bọc trong ```json ... ``` hoặc kèm lời dẫn."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Model trả về nội dung rỗng.")

    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Model có thể trả nhiều object nối tiếp (mỗi node một object) hoặc kèm
    # lời dẫn. Quét từng object và chọn object đúng cấu trúc graph.
    decoder = json.JSONDecoder()
    index = 0
    first_object = None

    while True:
        start = raw.find("{", index)
        if start == -1:
            break
        try:
            obj, consumed = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue

        if isinstance(obj, dict):
            if "nodes" in obj or "relationships" in obj:
                return obj
            first_object = first_object or obj
        index = start + consumed

    if first_object is not None:
        return first_object

    raise ValueError(f"Không tìm thấy JSON object trong phản hồi: {raw[:200]!r}")


def _validate_payload(data) -> dict:
    """Chuẩn hoá payload theo schema, báo lỗi rõ nếu sai cấu trúc."""
    return KnowledgeGraphExtraction.model_validate(data).model_dump()


def _call_json_mode(client, messages):
    """Gọi model ở JSON mode; nếu gateway không hỗ trợ thì gọi text thường.

    Không gửi schema/response_format kiểu ép kiểu: model tự sinh JSON theo
    system prompt. `{"type": "json_object"}` chỉ đảm bảo đầu ra là JSON hợp lệ.
    Trả về (data, usage, mode).
    """
    last_error = None
    for label, response_format in (("json_object", {"type": "json_object"}), ("plain json", None)):
        kwargs = dict(model=MODEL_NAME, messages=messages, temperature=TEMPERATURE)
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            completion = client.chat.completions.create(**kwargs)
            return (
                _parse_json_loose(completion.choices[0].message.content),
                _usage_dict(completion),
                label,
            )
        except openai.BadRequestError as exc:
            # Gateway không hỗ trợ response_format -> thử lại không kèm tham số này.
            last_error = exc
            continue

    raise last_error if last_error else RuntimeError("Gọi JSON mode thất bại.")


def preflight(client) -> bool:
    """Kiểm tra nhanh 9router sống và model có tồn tại."""
    try:
        available = [m.id for m in client.models.list().data]
    except openai.APIConnectionError as exc:
        print(f"❌ Không kết nối được 9router tại {BASE_URL}")
        print(f"   Chi tiết: {exc}")
        print("   Kiểm tra: 9router đang chạy? Thử `curl http://localhost:20128/v1/models`")
        return False
    except Exception as exc:
        # Gateway không hỗ trợ /models: vẫn cho chạy tiếp.
        print(f"⚠️  Không kiểm tra được danh sách model ({type(exc).__name__}). Vẫn thử chạy...")
        return True

    if available and MODEL_NAME not in available:
        print(f"❌ Model '{MODEL_NAME}' không có trong 9router.")
        similar = [m for m in available if "gemini" in m][:10]
        if similar:
            print("   Model gemini đang có: " + ", ".join(similar))
        return False

    print(f"✅ 9router OK: {len(available)} model khả dụng, '{MODEL_NAME}' có mặt.")
    return True


def run_extraction_9router(system_prompt: str):
    """
    Gửi request tới 9router gateway và lấy JSON output.
    Trả về (data, elapsed, usage, mode) hoặc (None, elapsed, None, None).
    """
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
    )

    print(f"🚀 9router: {BASE_URL}")
    print(f"   Model: {MODEL_NAME} | timeout: {REQUEST_TIMEOUT:.0f}s | retries: {MAX_RETRIES}")

    if not preflight(client):
        return None, 0.0, None, None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"VĂN BẢN LUẬT CẦN TRÍCH XUẤT:\n{SAMPLE_LAW_TEXT}"},
    ]

    started = time.perf_counter()

    try:
        data, usage, mode = _call_json_mode(client, messages)
    except (openai.APIConnectionError, openai.AuthenticationError,
            openai.PermissionDeniedError, openai.NotFoundError,
            openai.RateLimitError) as exc:
        elapsed = time.perf_counter() - started
        print(f"❌ Gọi API thất bại sau {elapsed:.2f}s: {type(exc).__name__}: {exc}")
        return None, elapsed, None, None
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"❌ Không lấy được JSON sau {elapsed:.2f}s: "
              f"{type(exc).__name__}: {str(exc)[:500]}")
        return None, elapsed, None, None

    elapsed = time.perf_counter() - started

    try:
        data = _validate_payload(data)
    except ValidationError as exc:
        print(f"❌ JSON trả về không khớp schema: {exc}")
        return None, elapsed, usage, None

    return data, elapsed, usage, mode

# ==========================================
# 7. IN KẾT QUẢ VÀ KIỂM TRA SCHEMA
# ==========================================

def print_and_verify(extracted_data: dict, elapsed_time: float, usage: dict,
                     mode: str, valid_classes: list, valid_relations: list,
                     output_file: str = "out.txt"):
    nodes = [n for n in extracted_data.get("nodes", []) if isinstance(n, dict)]
    relationships = [r for r in extracted_data.get("relationships", []) if isinstance(r, dict)]

    print("\n" + "=" * 60)
    print("📌 KẾT QUẢ TRÍCH XUẤT ĐẦU RA")
    print("=" * 60)

    abs_path = os.path.abspath(output_file)
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"💾 Đã lưu JSON vào: {abs_path}")
    except OSError as exc:
        print(f"❌ Không ghi được file {abs_path}: {exc}")

    if PRINT_JSON:
        print("\n" + "-" * 60)
        print(json.dumps(extracted_data, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("📊 BÁO CÁO KIỂM TRA NHANH (SCHEMA COMPLIANCE CHECK)")
    print("=" * 60)
    print(f"🔧  Chế độ gọi     : {mode}")
    print(f"⏱️  Thời gian phản hồi (Latency): {elapsed_time:.2f} giây")
    if usage:
        print(f"🎫  Tokens          : {usage.get('prompt', 0)} prompt / "
              f"{usage.get('completion', 0)} completion / {usage.get('total', 0)} total")
    print(f"📦  Tổng số Nodes  : {len(nodes)}")
    print(f"🔗  Tổng số Relationships: {len(relationships)}")

    node_ids = [n.get("id") for n in nodes]
    duplicate_ids = sorted({i for i in node_ids if i and node_ids.count(i) > 1})

    # Kiểm tra tính hợp lệ của Classes
    invalid_classes = [n for n in nodes if n.get("class_label") not in valid_classes]
    # Kiểm tra tính hợp lệ của Relations
    invalid_relations = [r for r in relationships if r.get("relation_type") not in valid_relations]
    # Kiểm tra relation trỏ tới node không tồn tại
    dangling = [
        r for r in relationships
        if r.get("source_id") not in node_ids or r.get("target_id") not in node_ids
    ]

    if not nodes:
        print("❌  Không có Node nào được trích xuất.")
    elif not invalid_classes:
        print("✅  Classes: 100% hợp lệ thuộc Ontology v9.0!")
    else:
        print(f"❌  Classes sai: {[n.get('class_label') for n in invalid_classes]}")

    if not relationships:
        print("❌  Không có Relationship nào được trích xuất.")
    elif not invalid_relations:
        print("✅  Relationships: 100% hợp lệ thuộc Ontology v9.0!")
    else:
        print(f"❌  Relationships sai: {[r.get('relation_type') for r in invalid_relations]}")

    if duplicate_ids:
        print(f"⚠️  Node ID trùng lặp: {duplicate_ids}")
    elif nodes:
        print("✅  Node ID: không trùng lặp.")

    if dangling:
        print(f"⚠️  {len(dangling)} relationship trỏ tới node không tồn tại "
              f"(vd: {dangling[0].get('source_id')} -> {dangling[0].get('target_id')}).")
    elif relationships:
        print("✅  Relationships: mọi source_id/target_id đều tồn tại trong nodes.")

    print("=" * 60 + "\n")

# ==========================================
# 8. MAIN ENTRYPOINT
# ==========================================

def main() -> int:
    print("=== TOOL CALLING TESTER (JSON OUTPUT ONLY) ===")
    print(f"🐍 Python {sys.version.split()[0]} | openai {openai.__version__} | {sys.executable}")

    try:
        _, valid_classes, valid_relations, system_prompt = load_ontology(ONTOLOGY_FILE)
        print(f"✅ Đã nạp thành công '{ONTOLOGY_FILE}': "
              f"{len(valid_classes)} Classes, {len(valid_relations)} Relations.")
    except Exception as exc:
        print(f"❌ Lỗi nạp Ontology: {exc}")
        return 1

    data, elapsed, usage, mode = run_extraction_9router(system_prompt)

    if not data:
        print("\n❌ Không lấy được kết quả trích xuất.")
        print("   Gợi ý: kiểm tra 9router, tên model, hoặc tăng REQUEST_TIMEOUT (vd: 600).")
        return 1

    print_and_verify(data, elapsed, usage, mode, valid_classes, valid_relations, OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
