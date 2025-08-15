import tkinter as tk
from tkinter import messagebox
import time
import random
import os

# --- 불러올 파일 이름 목록 ---
# 이제 한글과 영문 파일을 모두 포함합니다.
FILE_NAMES = [
    # 한글 파일
    "동백꽃.txt",
    "두형제와황금.txt",
    "운수좋은날.txt",
    "메밀꽃 필 무렵.txt",
    # 영문 파일
    "l_eng1.dat",
    "l_eng2.dat",
    "l_eng3.dat",
    "l_eng4.dat",
    "l_eng5.dat",
    "l_eng6.dat",
    "l_eng7.dat"
]

class TimedTypingTestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("한/영 타자연습 (3분)")
        self.root.geometry("800x600")

        self.setup_ui()
        self.reset_game()

    def setup_ui(self):
        """UI 요소들을 설정하고 배치합니다."""
        self.frame = tk.Frame(self.root, padx=10, pady=10)
        self.frame.pack(fill="both", expand=True)
        
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        # 원문 텍스트 박스
        prompt_frame = tk.Frame(self.frame)
        prompt_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        self.prompt_text = tk.Text(prompt_frame, font=("Malgun Gothic", 16), wrap="word", padx=10, pady=10, spacing1=5)
        self.prompt_scrollbar = tk.Scrollbar(prompt_frame, command=self.prompt_text.yview)
        self.prompt_text.config(yscrollcommand=self.prompt_scrollbar.set)
        
        self.prompt_scrollbar.pack(side="right", fill="y")
        self.prompt_text.pack(side="left", fill="both", expand=True)

        # 사용자 입력 텍스트 박스
        input_frame = tk.Frame(self.frame)
        input_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.input_text = tk.Text(input_frame, font=("Malgun Gothic", 16), wrap="word", padx=10, pady=10, spacing1=5)
        self.input_scrollbar = tk.Scrollbar(input_frame, command=self.input_text.yview)
        self.input_text.config(yscrollcommand=self.input_scrollbar.set)
        
        self.input_scrollbar.pack(side="right", fill="y")
        self.input_text.pack(side="left", fill="both", expand=True)

        # 통계 및 버튼
        self.stats_label = tk.Label(self.frame, text="남은 시간: 3:00 | 속도: 0타/분 | 정확도: 100.0%", font=("Malgun Gothic", 14))
        self.stats_label.grid(row=2, column=0, pady=10)

        self.reset_button = tk.Button(self.frame, text="다른 글로 다시 시작", font=("Malgun Gothic", 14), command=self.reset_game)
        self.reset_button.grid(row=3, column=0, pady=5)

    def load_text_from_file(self):
        """파일 목록에서 무작위로 하나를 선택하여 내용을 읽어옵니다."""
        chosen_file = ""
        try:
            chosen_file = random.choice(FILE_NAMES)
            # utf-8-sig 인코딩으로 파일을 열어보고, 실패 시 다른 인코딩으로 재시도
            try:
                with open(chosen_file, 'r', encoding='utf-8-sig') as f:
                    return f.read().strip().replace('\r\n', '\n')
            except UnicodeDecodeError:
                # 영문 파일 등을 위한 기본 인코딩(cp949 등)으로 재시도
                with open(chosen_file, 'r', encoding='cp949') as f:
                    return f.read().strip().replace('\r\n', '\n')
        except FileNotFoundError:
            error_msg = f"파일을 찾을 수 없습니다: '{chosen_file}'\n\n실행 파일(.py)과 텍스트 파일(.txt, .dat)이 같은 폴더에 있는지 확인해주세요."
            messagebox.showerror("파일 오류", error_msg)
            self.root.quit()
            return None
        except Exception as e:
            error_msg = f"파일을 읽는 중 오류가 발생했습니다: {e}"
            messagebox.showerror("오류", error_msg)
            self.root.quit()
            return None


    def reset_game(self):
        """게임을 초기 상태로 되돌립니다."""
        if hasattr(self, 'timer_job'):
            self.root.after_cancel(self.timer_job)
        if hasattr(self, 'polling_job'):
            self.root.after_cancel(self.polling_job)

        self.game_running = False
        self.start_time = None
        self.time_limit = 180  # 3분

        self.current_prompt_text = self.load_text_from_file()
        if self.current_prompt_text is None: return

        self.prompt_text.config(state="normal")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", self.current_prompt_text)
        self.prompt_text.config(state="disabled")

        self.prompt_text.tag_config("correct", foreground="gray")
        self.prompt_text.tag_config("incorrect", foreground="red", underline=True)
        self.prompt_text.tag_config("cursor", background="#FFFF99")

        self.input_text.config(state="normal")
        self.input_text.delete("1.0", tk.END)
        self.input_text.focus()
        
        self.input_text.bind("<KeyPress>", self.process_key_press)
        self.input_text.bind("<KeyRelease>", self.process_key_release)


        self.stats_label.config(text=f"남은 시간: {self.time_limit//60}:{self.time_limit%60:02d} | 속도: 0타/분 | 정확도: 100.0%")

    def process_key_press(self, event):
        """키를 누를 때 호출됩니다. (게임 시작 및 자동 줄바꿈 처리)"""
        if not self.game_running:
            if event.keysym not in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Tab", "Hangul"):
                self.game_running = True
                self.start_time = time.time()
                self.update_timer()

        if event.keysym == "space":
            # ### FIX: 커서 위치 계산 방식을 변경하여 줄바꿈 오류 수정 ###
            # 시작부터 현재 커서까지의 텍스트를 가져와 그 길이를 현재 위치로 사용합니다.
            text_before_cursor = self.input_text.get("1.0", tk.INSERT)
            current_pos = len(text_before_cursor)
            
            if current_pos < len(self.current_prompt_text) and self.current_prompt_text[current_pos] == '\n':
                self.input_text.insert(tk.INSERT, "\n")
                return "break" 

    def process_key_release(self, event):
        """키에서 손을 뗄 때(글자 조합 완료 후) 오타 및 통계를 처리합니다."""
        if self.game_running:
            self.update_stats_and_colors()


    def update_stats_and_colors(self):
        """통계와 텍스트 색상을 업데이트합니다."""
        if not self.game_running: return

        typed_text = self.input_text.get("1.0", "end-1c")
        
        self.prompt_text.tag_remove("correct", "1.0", tk.END)
        self.prompt_text.tag_remove("incorrect", "1.0", tk.END)
        self.prompt_text.tag_remove("cursor", "1.0", tk.END)

        correct_chars = 0
        
        for i, char in enumerate(typed_text):
            if i < len(self.current_prompt_text):
                prompt_char = self.current_prompt_text[i]
                
                widget_index = self.prompt_text.index(f"1.0 + {i} chars")

                if char == prompt_char:
                    self.prompt_text.tag_add("correct", widget_index)
                    correct_chars += 1
                else:
                    self.prompt_text.tag_add("incorrect", widget_index)
        
        cursor_pos = len(typed_text)
        if cursor_pos < len(self.current_prompt_text):
            cursor_widget_index = self.prompt_text.index(f"1.0 + {cursor_pos} chars")
            self.prompt_text.tag_add("cursor", cursor_widget_index)
            self.prompt_text.see(cursor_widget_index)

        elapsed_time = time.time() - self.start_time
        cpm = (correct_chars / elapsed_time) * 60 if elapsed_time > 0 else 0
        accuracy = (correct_chars / len(typed_text)) * 100 if len(typed_text) > 0 else 100.0

        current_time_text = self.stats_label.cget("text").split("|")[0].strip()
        self.stats_label.config(text=f"{current_time_text} | 속도: {cpm:.0f}타/분 | 정확도: {accuracy:.1f}%")

    def update_timer(self):
        """1초마다 타이머를 업데이트합니다."""
        if not self.game_running: return

        elapsed_time = time.time() - self.start_time
        remaining_time = self.time_limit - elapsed_time

        if remaining_time <= 0:
            self.end_game()
            return
        
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        current_stats_text = self.stats_label.cget("text").split("|", 1)[1].strip()
        self.stats_label.config(text=f"남은 시간: {minutes}:{seconds:02d} | {current_stats_text}")
        
        self.timer_job = self.root.after(1000, self.update_timer)

    def end_game(self):
        """게임이 종료될 때 호출됩니다."""
        self.game_running = False
        self.input_text.config(state="disabled")
        self.stats_label.config(text="시간 종료!")

        typed_text = self.input_text.get("1.0", "end-1c")
        
        correct_chars = 0
        for i, char in enumerate(typed_text):
            if i < len(self.current_prompt_text) and char == self.current_prompt_text[i]:
                correct_chars += 1

        cpm = (correct_chars / self.time_limit) * 60
        accuracy = (correct_chars / len(typed_text)) * 100 if len(typed_text) > 0 else 100.0

        final_message = (f"🎉 3분 종료! 🎉\n\n"
                         f"- 평균 속도: {cpm:.0f}타/분\n"
                         f"- 정확도: {accuracy:.1f}%")
        messagebox.showinfo("결과", final_message)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimedTypingTestApp(root)
    root.mainloop()
