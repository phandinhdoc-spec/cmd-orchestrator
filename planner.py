from __future__ import annotations
import re

def classify(req: str):
    s=req.lower()
    complexity="direct"
    if any(x in s for x in ("toàn bộ","whole project","nhiều file","backend","android","esp32","refactor","kiểm thử","test toàn","triển khai")):
        complexity="sequential"
    if any(x in s for x in ("song song","parallel","frontend và backend","android và esp","nhiều module")):
        complexity="parallel"
    return complexity

def plan(req: str):
    c=classify(req)
    if c=="direct":
        tasks=[{
            "id":"T1","title":"Thực hiện yêu cầu","description":req,
            "dependencies":[],"task_class":"general","risk":"low",
            "verification":"Kiểm tra diff/output thực tế và chạy kiểm tra phù hợp."
        }]
    else:
        tasks=[
          {"id":"T1","title":"Khảo sát tối thiểu","description":"Chỉ đọc file/cấu trúc liên quan; dùng rg/find/sed, không quét toàn repo.",
           "dependencies":[],"task_class":"inspect","risk":"low","verification":"Xác định đúng file/phạm vi và ràng buộc."},
          {"id":"T2","title":"Triển khai chính","description":req,
           "dependencies":["T1"],"task_class":"implementation","risk":"medium","verification":"Kiểm tra diff và hành vi chính."},
          {"id":"T3","title":"Kiểm chứng","description":"Chạy test/build/lint hoặc kiểm tra thực tế phù hợp; không tin self-report của worker.",
           "dependencies":["T2"],"task_class":"verification","risk":"medium","verification":"Có bằng chứng test/build/verification."},
          {"id":"T4","title":"Hoàn tất","description":"Tóm tắt thay đổi, bảo đảm không có secret/file rác; nếu project có quy tắc GitHub thì commit/push.",
           "dependencies":["T3"],"task_class":"finalize","risk":"low","verification":"Trạng thái cuối nhất quán; Git sạch hoặc thay đổi được giải thích."}
        ]
    return {"summary":req[:500],"complexity":c,"tasks":tasks}
