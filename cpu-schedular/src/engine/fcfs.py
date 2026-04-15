import tkinter as tk
from tkinter import messagebox
import time
import threading

class FCFSScheduler:
    def __init__(self, root):
        self.root = root
        self.root.title("CPU Scheduler - FCFS Mode")

        self.processes = []  # [PID, Arrival, Burst, Remaining, Finish, TAT, WT]
        self.current_time = 0
        self.running = False
        self.gantt = []  # (PID, start, end)

        # GUI
        tk.Label(root, text="Process ID:").grid(row=0, column=0)
        self.pid_entry = tk.Entry(root)
        self.pid_entry.grid(row=0, column=1)

        tk.Label(root, text="Arrival Time:").grid(row=1, column=0)
        self.arrival_entry = tk.Entry(root)
        self.arrival_entry.grid(row=1, column=1)

        tk.Label(root, text="Burst Time:").grid(row=2, column=0)
        self.burst_entry = tk.Entry(root)
        self.burst_entry.grid(row=2, column=1)

        tk.Button(root, text="Add Process", command=self.add_process).grid(row=3, column=0, columnspan=2)
        tk.Button(root, text="Start Live Scheduler", command=self.start_thread).grid(row=4, column=0, columnspan=2)
        tk.Button(root, text="Run Instantly", command=self.run_instant).grid(row=5, column=0, columnspan=2)

        self.status_label = tk.Label(root, text="Status: Waiting", fg="blue")
        self.status_label.grid(row=6, column=0, columnspan=2)

        self.table_text = tk.Text(root, height=10, width=40)
        self.table_text.grid(row=7, column=0, columnspan=2)

        self.gantt_text = tk.Text(root, height=5, width=40)
        self.gantt_text.grid(row=8, column=0, columnspan=2)

    # ----------------------
    def add_process(self):
        try:
            pid = self.pid_entry.get()
            arrival = int(self.arrival_entry.get())
            burst = int(self.burst_entry.get())

            self.processes.append([pid, arrival, burst, burst, 0, 0, 0])

            messagebox.showinfo("Success", f"Process {pid} added!")

            # clear fields
            self.pid_entry.delete(0, tk.END)
            self.arrival_entry.delete(0, tk.END)
            self.burst_entry.delete(0, tk.END)

            self.update_table()

        except ValueError:
            messagebox.showerror("Error", "Enter valid numbers.")

    # ----------------------
    def update_table(self):
        self.table_text.delete('1.0', tk.END)
        self.table_text.insert(tk.END, "PID | Arrival | Remaining\n")
        self.table_text.insert(tk.END, "-"*30 + "\n")
        for p in self.processes:
            self.table_text.insert(tk.END, f"{p[0]} | {p[1]} | {p[3]}\n")

    # ----------------------
    def update_gantt(self):
        self.gantt_text.delete('1.0', tk.END)
        timeline = ""
        times = ""

        for pid, start, end in self.gantt:
            timeline += f"| {pid} "
            times += f"{start}   "

        if self.gantt:
            times += str(self.gantt[-1][2])

        self.gantt_text.insert(tk.END, timeline + "|\n")
        self.gantt_text.insert(tk.END, times)

    # ----------------------
    def run_scheduler(self, live=True):
        self.running = True
        self.processes.sort(key=lambda x: x[1])

        for p in self.processes:
            if self.current_time < p[1]:
                idle = p[1] - self.current_time
                if live:
                    time.sleep(idle)
                self.current_time += idle

            start = self.current_time
            burst = p[3]

            # Update UI safely
            self.root.after(0, lambda pid=p[0]: self.status_label.config(text=f"Running: {pid}"))

            if live:
                time.sleep(burst)

            self.current_time += burst
            p[3] = 0

            end = self.current_time
            self.gantt.append((p[0], start, end))

            # Calculations
            p[4] = end
            p[5] = p[4] - p[1]
            p[6] = p[5] - p[2]

            # Update UI
            self.root.after(0, self.update_table)
            self.root.after(0, self.update_gantt)

        self.root.after(0, self.calculate_averages)

    # ----------------------
    def start_thread(self):
        if not self.running:
            threading.Thread(target=self.run_scheduler, daemon=True).start()

    # ----------------------
    def run_instant(self):
        if not self.running:
            self.run_scheduler(live=False)

    # ----------------------
    def calculate_averages(self):
        total_wt = sum(p[6] for p in self.processes)
        total_tat = sum(p[5] for p in self.processes)
        n = len(self.processes)

        avg_wt = total_wt / n
        avg_tat = total_tat / n

        messagebox.showinfo("Results",
                            f"Average Waiting Time: {avg_wt:.2f}\n"
                            f"Average Turnaround Time: {avg_tat:.2f}")

        self.running = False


# ----------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = FCFSScheduler(root)
    root.mainloop()