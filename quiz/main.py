import streamlit as st
from openai import OpenAI
import time
import PyPDF2
import pytesseract
from pdf2image import convert_from_bytes
import json

# 1. CẤU HÌNH GIAO DIỆN TRANG WEB
st.set_page_config(page_title="Tạo Câu Hỏi Trắc Nghiệm", page_icon="📝", layout="centered")
st.title("Web Tạo Câu Hỏi & Thi Trắc Nghiệm")

# --- KHỞI TẠO BỘ NHỚ TRẠNG THÁI (SESSION STATE) ---
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
    
# Bộ nhớ đệm tài liệu (Tối ưu tốc độ tải file)
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "current_file_name" not in st.session_state:
    st.session_state.current_file_name = ""
    
# Bộ nhớ câu hỏi cũ (Chống trùng lặp)
if "history_questions" not in st.session_state:
    st.session_state.history_questions = []

# 2. CẤU HÌNH FIREWORKS AI
try:
    API_KEY = st.secrets["FIREWORKS_AI_API_KEY"]
    client = OpenAI(
        base_url="https://api.fireworks.ai/inference/v1",
        api_key=API_KEY
    )
except Exception:
    st.error("Chưa cấu hình API Key trong hệ thống (.streamlit/secrets.toml)")
    st.stop()

# 3. GIAO DIỆN NHẬP TÀI LIỆU
st.subheader("1. Cung cấp tài liệu")
input_method = st.radio("Chọn cách nhập tài liệu:", ("Tải lên file (.pdf)", "Dán văn bản"))

document_text = ""

if input_method == "Tải lên file (.pdf)":
    uploaded_file = st.file_uploader("Chọn file PDF của bạn", type=["pdf"])
    
    if uploaded_file is not None:
        # Nếu là file mới hoàn toàn
        if uploaded_file.name != st.session_state.current_file_name:
            st.session_state.current_file_name = uploaded_file.name
            st.session_state.extracted_text = ""
            st.session_state.history_questions = [] # Reset lại lịch sử câu hỏi vì là file mới
            temp_text = ""
            
            with st.spinner("Đang phân tích và đọc tài liệu..."):
                try:
                    uploaded_file.seek(0) 
                    pdf_reader = PyPDF2.PdfReader(uploaded_file)
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            temp_text += text + "\n"
                    
                    # Fallback quét OCR nếu PDF là dạng ảnh
                    if not temp_text.strip():
                        st.info("Phát hiện PDF dạng ảnh. Đang tiến hành quét OCR...")
                        # Dành cho Windows, bỏ comment dòng dưới và trỏ đúng đường dẫn
                        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                        
                        uploaded_file.seek(0)
                        pdf_bytes = uploaded_file.read()
                        pages_as_images = convert_from_bytes(pdf_bytes)
                        
                        for img in pages_as_images:
                            extracted_text = pytesseract.image_to_string(img, lang='vie+eng')
                            temp_text += extracted_text + "\n"
                        
                        if temp_text.strip():
                            st.success("Đã trích xuất chữ bằng OCR thành công!")
                        else:
                            st.error("Tài liệu quá mờ hoặc không có chữ.")
                    else:
                        st.success("Đã đọc thành công nội dung file PDF!")
                        
                    # Lưu vào bộ nhớ đệm
                    st.session_state.extracted_text = temp_text
                    document_text = temp_text
                    
                except Exception as e:
                    st.error(f"Lỗi khi đọc file: {e}")
        else:
            # Nếu là file cũ: Lấy thẳng text từ bộ nhớ ra dùng
            document_text = st.session_state.extracted_text
            
    else:
        # Nếu người dùng bấm dấu X tắt file
        st.session_state.current_file_name = ""
        st.session_state.extracted_text = ""
        st.session_state.history_questions = []
else:
    document_text = st.text_area("Dán nội dung tài liệu vào đây:", height=200)


# 4. GIAO DIỆN CẤU HÌNH & TẠO CÂU HỎI
st.subheader("2. Cấu hình sinh câu hỏi")

col1, col2 = st.columns([3, 2])
with col1:
    num_questions = st.number_input("Số lượng câu hỏi cần tạo:", min_value=1, max_value=50, value=5)
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Xóa bộ nhớ đệm"):
        st.session_state.history_questions = []
        st.success("Đã reset! AI sẽ quét lại tài liệu từ đầu.")

if st.button("Tạo Bộ Câu Hỏi", type="primary"):
    if not document_text.strip():
        st.warning("Vui lòng cung cấp nội dung tài liệu.")
    else:
        # Xóa bài thi hiện tại để chuẩn bị tạo bài mới
        st.session_state.quiz_data = None
        st.session_state.quiz_submitted = False
        for key in list(st.session_state.keys()):
            if key.startswith("user_ans_"):
                del st.session_state[key]
        
        # Gom các câu hỏi cũ thành 1 chuỗi văn bản để làm nhiễu
        if len(st.session_state.history_questions) > 0:
            history_text = "\n- ".join(st.session_state.history_questions)
            history_instruction = f"CÁC CÂU HỎI ĐÃ TẠO TRƯỚC ĐÓ (TUYỆT ĐỐI KHÔNG HỎI LẠI CÁC Ý NÀY):\n- {history_text}"
        else:
            history_instruction = "Đây là lần tạo đầu tiên, bạn có thể tự do khai thác mọi ý chính và phụ trong tài liệu."
        
        # Khởi tạo Prompt
        prompt = f"""
        Bạn là một chuyên gia giáo dục. Dựa vào nội dung tài liệu dưới đây, hãy tạo ra {num_questions} câu hỏi trắc nghiệm.
        
        {history_instruction}
        
        YÊU CẦU QUAN TRỌNG NHẤT: BẠN PHẢI TRẢ VỀ DỮ LIỆU DƯỚI ĐỊNH DẠNG MẢNG JSON. Không kèm theo bất kỳ văn bản nào khác.
        
        Cấu trúc JSON bắt buộc:
        [
            {{
                "question": "Nội dung câu hỏi...",
                "options": ["A. Đáp án 1", "B. Đáp án 2", "C. Đáp án 3", "D. Đáp án 4"],
                "answer": "A", // Chỉ ghi 1 chữ cái in hoa (A, B, C hoặc D)
                "explanation": "Giải thích chi tiết..."
            }}
        ]

        TÀI LIỆU (Mã phiên: {time.time()}):
        {document_text}
        """

        with st.spinner("Đang biên soạn câu hỏi..."):
            try:
                response = client.chat.completions.create(
                    model="accounts/fireworks/models/minimax-m3",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8
                )
                
                # Bóc tách JSON
                raw_json = response.choices[0].message.content
                clean_json = raw_json.replace("```json", "").replace("```", "").strip()
                
                new_quiz_data = json.loads(clean_json)
                st.session_state.quiz_data = new_quiz_data
                
                # Lưu câu hỏi vừa tạo vào bộ nhớ chống trùng lặp
                for q in new_quiz_data:
                    st.session_state.history_questions.append(q["question"])
                
                st.success("Tạo câu hỏi thành công! Kéo xuống để bắt đầu làm bài.")
                
            except json.JSONDecodeError:
                st.error("Lỗi: AI không trả về đúng định dạng chuẩn. Vui lòng bấm tạo lại.")
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")

# 5. HIỂN THỊ GIAO DIỆN LÀM BÀI TƯƠNG TÁC
if st.session_state.quiz_data:
    st.markdown("---")
    st.header("📝 BÀI KIỂM TRA")
    
    with st.form("quiz_form"):
        for i, q in enumerate(st.session_state.quiz_data):
            st.markdown(f"**Câu {i+1}: {q['question']}**")
            st.radio(
                "Chọn đáp án:", 
                q['options'], 
                key=f"user_ans_{i}", 
                index=None,
                label_visibility="collapsed"
            )
            st.write("") 
            
        submitted = st.form_submit_button("Nộp Bài & Xem Điểm", type="primary")
        if submitted:
            st.session_state.quiz_submitted = True

    # 6. HIỂN THỊ KẾT QUẢ & NÚT LÀM LẠI
    if st.session_state.quiz_submitted:
        st.markdown("---")
        st.header("📊 KẾT QUẢ BÀI LÀM")
        
        score = 0
        total_q = len(st.session_state.quiz_data)
        
        for i, q in enumerate(st.session_state.quiz_data):
            user_choice = st.session_state.get(f"user_ans_{i}")
            correct_letter = q['answer'].strip()
            
            is_correct = user_choice is not None and user_choice.startswith(correct_letter)
            
            with st.expander(f"Câu {i+1}: {'✅ ĐÚNG' if is_correct else '❌ SAI'}", expanded=True):
                st.write(f"**Câu hỏi:** {q['question']}")
                
                if user_choice is None:
                    st.warning("Bạn chưa chọn đáp án cho câu này.")
                elif is_correct:
                    score += 1
                    st.success(f"**Bạn chọn:** {user_choice} (Chính xác!)")
                else:
                    correct_full = next((opt for opt in q['options'] if opt.startswith(correct_letter)), correct_letter)
                    st.error(f"**Bạn chọn:** {user_choice}")
                    st.info(f"**Đáp án đúng:** {correct_full}")
                
                st.write(f"**Giải thích:** {q['explanation']}")
                
        st.metric(label="Điểm số của bạn", value=f"{score} / {total_q}")
        
        if score == total_q:
            st.balloons()
            
        # --- NÚT LÀM LẠI BÀI ---
        st.markdown("<br>", unsafe_allow_html=True) 
        
        if st.button("🔄 Làm lại bài này"):
            # Gỡ trạng thái đã nộp bài
            st.session_state.quiz_submitted = False
            # Xóa sạch các tick chọn đáp án cũ
            for key in list(st.session_state.keys()):
                if key.startswith("user_ans_"):
                    del st.session_state[key]
            # Tải lại trang ngay lập tức
            st.rerun()