# ui.py — All windows and interface components

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db

# ── COLORS & FONTS ──
PRIMARY    = "#0a3d62"
SECONDARY  = "#1e6fa8"
ACCENT     = "#e8a020"
SUCCESS    = "#1a9e6e"
DANGER     = "#d94f3d"
BG         = "#f0f5fa"
WHITE      = "#ffffff"
MUTED      = "#8a9bb0"
FONT_TITLE = ("Georgia", 20, "bold")
FONT_HEAD  = ("Georgia", 13, "bold")
FONT_BODY  = ("Helvetica", 11)
FONT_SMALL = ("Helvetica", 9)

def style_button(btn, color=PRIMARY, fg=WHITE):
    btn.configure(
        bg=color, fg=fg,
        font=("Helvetica", 10, "bold"),
        relief="flat", cursor="hand2",
        padx=16, pady=8,
        activebackground=SECONDARY,
        activeforeground=WHITE,
        bd=0
    )

def label(parent, text, font=FONT_BODY, color=PRIMARY, **kwargs):
    return tk.Label(parent, text=text, font=font, fg=color, bg=parent["bg"] if "bg" in parent.keys() else BG, **kwargs)


# ══════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ══════════════════════════════════════════
class HospitalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StanCare — Hospital Patient Management System")
        self.geometry("1100x700")
        self.minsize(1000, 650)
        self.configure(bg=BG)
        self.resizable(True, True)

        db.initialize_db()
        self._build_layout()
        self.show_dashboard()

    def _build_layout(self):
        # ── Sidebar
        self.sidebar = tk.Frame(self, bg=PRIMARY, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(self.sidebar, bg=PRIMARY, pady=20)
        logo_frame.pack(fill="x", padx=20)
        tk.Label(logo_frame, text="🏥", font=("Helvetica", 28), bg=PRIMARY, fg=WHITE).pack()
        tk.Label(logo_frame, text="StanCare", font=("Georgia", 16, "bold"), bg=PRIMARY, fg=WHITE).pack()
        tk.Label(logo_frame, text="Hospital Management", font=("Helvetica", 8), bg=PRIMARY, fg=MUTED).pack()
        tk.Frame(self.sidebar, bg=WHITE, height=1, pady=0).pack(fill="x", padx=20, pady=10)

        # Nav buttons
        self.nav_buttons = []
        nav_items = [
            ("⊞  Dashboard",    self.show_dashboard),
            ("👥  Patients",     self.show_patients),
            ("📅  Appointments", self.show_appointments),
            ("🔍  Search",       self.show_search),
        ]
        for label_text, command in nav_items:
            btn = tk.Button(
                self.sidebar, text=label_text,
                font=("Helvetica", 10), fg=WHITE, bg=PRIMARY,
                relief="flat", anchor="w", padx=20, pady=12,
                cursor="hand2", activebackground=SECONDARY,
                activeforeground=WHITE, bd=0,
                command=command
            )
            btn.pack(fill="x")
            self.nav_buttons.append(btn)

        # Footer
        tk.Frame(self.sidebar, bg=PRIMARY).pack(fill="y", expand=True)
        tk.Label(self.sidebar, text=f"© {datetime.now().year} StanCare",
                 font=FONT_SMALL, bg=PRIMARY, fg=MUTED).pack(pady=16)

        # ── Main area
        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        # Top bar
        topbar = tk.Frame(self.main, bg=WHITE, height=60, bd=0,
                          highlightbackground="#dce6f0", highlightthickness=1)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        self.page_title = tk.Label(topbar, text="Dashboard", font=("Georgia", 15, "bold"),
                                   fg=PRIMARY, bg=WHITE)
        self.page_title.pack(side="left", padx=24, pady=16)

        now = datetime.now().strftime("%A, %d %B %Y")
        tk.Label(topbar, text=now, font=FONT_SMALL, fg=MUTED, bg=WHITE).pack(side="right", padx=24)

        # Content frame
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=20)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def set_title(self, title):
        self.page_title.configure(text=title)

    # ══════════════════════════
    #  DASHBOARD
    # ══════════════════════════
    def show_dashboard(self):
        self.clear_content()
        self.set_title("Dashboard")
        stats = db.get_stats()

        # Stat cards
        cards_frame = tk.Frame(self.content, bg=BG)
        cards_frame.pack(fill="x", pady=(0, 20))

        card_data = [
            ("Total Patients",    str(stats["total"]),              PRIMARY,   "👥"),
            ("Active Patients",   str(stats["active"]),             SUCCESS,   "✅"),
            ("Discharged",        str(stats["discharged"]),         MUTED,     "🏠"),
            ("Appointments Today",str(stats["today_appointments"]), ACCENT,    "📅"),
        ]

        for i, (title, value, color, icon) in enumerate(card_data):
            card = tk.Frame(cards_frame, bg=WHITE, padx=20, pady=16,
                            highlightbackground="#dce6f0", highlightthickness=1)
            card.grid(row=0, column=i, padx=(0, 12) if i < 3 else 0, sticky="ew")
            cards_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=("Helvetica", 22), bg=WHITE).pack(anchor="w")
            tk.Label(card, text=value, font=("Georgia", 28, "bold"), fg=color, bg=WHITE).pack(anchor="w")
            tk.Label(card, text=title, font=FONT_SMALL, fg=MUTED, bg=WHITE).pack(anchor="w")

        # Recent patients table
        tk.Label(self.content, text="Recent Patients", font=FONT_HEAD,
                 fg=PRIMARY, bg=BG).pack(anchor="w", pady=(8, 10))

        self._render_patient_table(self.content, db.get_all_patients()[:8])

        # Quick action buttons
        btn_frame = tk.Frame(self.content, bg=BG)
        btn_frame.pack(fill="x", pady=(16, 0))
        add_btn = tk.Button(btn_frame, text="+ Register New Patient",
                            command=self.open_add_patient, **{})
        style_button(add_btn, PRIMARY)
        add_btn.pack(side="left", padx=(0, 10))

        appt_btn = tk.Button(btn_frame, text="📅 Book Appointment",
                             command=self.open_add_appointment)
        style_button(appt_btn, SECONDARY)
        appt_btn.pack(side="left")

    # ══════════════════════════
    #  PATIENTS PAGE
    # ══════════════════════════
    def show_patients(self):
        self.clear_content()
        self.set_title("Patients")

        # Action bar
        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Register New Patient", command=self.open_add_patient)
        style_button(add_btn)
        add_btn.pack(side="left")

        # Filter
        tk.Label(bar, text="Filter:", font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="right", padx=(0, 6))
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(bar, textvariable=self.filter_var,
                                    values=["All", "Active", "Discharged"],
                                    width=12, state="readonly")
        filter_combo.pack(side="right")
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_patient_list())

        # Table frame
        self.patient_table_frame = tk.Frame(self.content, bg=BG)
        self.patient_table_frame.pack(fill="both", expand=True)
        self._refresh_patient_list()

    def _refresh_patient_list(self):
        for w in self.patient_table_frame.winfo_children():
            w.destroy()
        f = self.filter_var.get() if hasattr(self, 'filter_var') else "All"
        if f == "Active":
            patients = db.get_active_patients()
        else:
            patients = db.get_all_patients()
            if f == "Discharged":
                patients = [p for p in patients if p[6] == "Discharged"]
        self._render_patient_table(self.patient_table_frame, patients, actions=True)

    def _render_patient_table(self, parent, patients, actions=False):
        cols = ("ID", "Name", "Age", "Gender", "Contact", "Condition", "Status", "Registered")
        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=WHITE, foreground=PRIMARY,
                        rowheight=30, fieldbackground=WHITE,
                        font=("Helvetica", 10))
        style.configure("Treeview.Heading",
                        background=PRIMARY, foreground=WHITE,
                        font=("Helvetica", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", SECONDARY)])

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        widths = [40, 160, 40, 70, 110, 150, 80, 130]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center" if col != "Name" and col != "Condition" else "w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for p in patients:
            reg_date = str(p[7])[:10] if len(p) > 7 and p[7] else ""
            status_tag = "active" if p[6] == "Active" else "discharged"
            tree.insert("", "end", values=(p[0], p[1], p[2], p[3], p[4], p[5], p[6], reg_date),
                        tags=(status_tag,))
        tree.tag_configure("active",     background="#f0fff8")
        tree.tag_configure("discharged", background="#fff5f5")

        if actions:
            btn_bar = tk.Frame(parent, bg=BG)
            btn_bar.pack(fill="x", pady=(10, 0))

            def discharge():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Select Patient", "Please select a patient first.")
                    return
                pid = tree.item(sel[0])["values"][0]
                name = tree.item(sel[0])["values"][1]
                if messagebox.askyesno("Discharge", f"Discharge {name}?"):
                    db.discharge_patient(pid)
                    self._refresh_patient_list()

            def delete():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Select Patient", "Please select a patient first.")
                    return
                pid = tree.item(sel[0])["values"][0]
                name = tree.item(sel[0])["values"][1]
                if messagebox.askyesno("Delete", f"Permanently delete {name}? This cannot be undone."):
                    db.delete_patient(pid)
                    self._refresh_patient_list()

            def book_appt():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Select Patient", "Please select a patient first.")
                    return
                pid  = tree.item(sel[0])["values"][0]
                name = tree.item(sel[0])["values"][1]
                self.open_add_appointment(pid, name)

            d_btn = tk.Button(btn_bar, text="✅ Discharge Selected", command=discharge)
            style_button(d_btn, SUCCESS)
            d_btn.pack(side="left", padx=(0, 8))

            a_btn = tk.Button(btn_bar, text="📅 Book Appointment", command=book_appt)
            style_button(a_btn, SECONDARY)
            a_btn.pack(side="left", padx=(0, 8))

            x_btn = tk.Button(btn_bar, text="🗑 Delete", command=delete)
            style_button(x_btn, DANGER)
            x_btn.pack(side="left")

    # ══════════════════════════
    #  APPOINTMENTS PAGE
    # ══════════════════════════
    def show_appointments(self):
        self.clear_content()
        self.set_title("Appointments")

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Book Appointment", command=self.open_add_appointment)
        style_button(add_btn)
        add_btn.pack(side="left")

        cols = ("ID", "Patient", "Doctor", "Date", "Time", "Notes", "Status")
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Treeview", rowheight=30, font=("Helvetica", 10))

        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = [40, 150, 140, 100, 80, 180, 90]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="w" if col in ("Patient","Doctor","Notes") else "center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for a in db.get_all_appointments():
            tag = "scheduled" if a[7] == "Scheduled" else "cancelled"
            tree.insert("", "end", values=(a[0], a[2], a[3], a[4], a[5], a[6] or "", a[7]), tags=(tag,))

        tree.tag_configure("scheduled", background="#f0fff8")
        tree.tag_configure("cancelled", background="#fff5f5")

        def cancel():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select an appointment.")
                return
            aid = tree.item(sel[0])["values"][0]
            if messagebox.askyesno("Cancel", "Cancel this appointment?"):
                db.cancel_appointment(aid)
                self.show_appointments()

        c_btn = tk.Button(self.content, text="✕ Cancel Appointment", command=cancel)
        style_button(c_btn, DANGER)
        c_btn.pack(anchor="w", pady=(10, 0))

    # ══════════════════════════
    #  SEARCH PAGE
    # ══════════════════════════
    def show_search(self):
        self.clear_content()
        self.set_title("Search Patients")

        search_frame = tk.Frame(self.content, bg=BG)
        search_frame.pack(fill="x", pady=(0, 20))

        tk.Label(search_frame, text="Search by Name or ID:", font=FONT_BODY,
                 fg=PRIMARY, bg=BG).pack(side="left", padx=(0, 10))

        self.search_var = tk.StringVar()
        entry = tk.Entry(search_frame, textvariable=self.search_var,
                         font=FONT_BODY, width=30, relief="flat",
                         highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        entry.pack(side="left", padx=(0, 10))
        entry.focus()

        self.search_result_frame = tk.Frame(self.content, bg=BG)
        self.search_result_frame.pack(fill="both", expand=True)

        def do_search(*args):
            q = self.search_var.get().strip()
            for w in self.search_result_frame.winfo_children():
                w.destroy()
            if q:
                results = db.search_patients(q)
                if results:
                    self._render_patient_table(self.search_result_frame, results)
                else:
                    tk.Label(self.search_result_frame, text="No patients found.",
                             font=FONT_BODY, fg=MUTED, bg=BG).pack(pady=30)

        s_btn = tk.Button(search_frame, text="Search", command=do_search)
        style_button(s_btn)
        s_btn.pack(side="left")
        self.search_var.trace("w", do_search)

    # ══════════════════════════
    #  ADD PATIENT MODAL
    # ══════════════════════════
    def open_add_patient(self):
        win = tk.Toplevel(self)
        win.title("Register New Patient")
        win.geometry("460x480")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Register New Patient", font=FONT_TITLE,
                 fg=PRIMARY, bg=BG).pack(pady=(20, 4))
        tk.Label(win, text="Fill in all fields below", font=FONT_SMALL,
                 fg=MUTED, bg=BG).pack(pady=(0, 16))

        form = tk.Frame(win, bg=BG, padx=40)
        form.pack(fill="x")

        fields = {}
        field_list = [
            ("Full Name",  "name"),
            ("Age",        "age"),
            ("Contact",    "contact"),
            ("Condition",  "condition"),
        ]
        for label_text, key in field_list:
            tk.Label(form, text=label_text, font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
            e = tk.Entry(form, font=FONT_BODY, relief="flat",
                         highlightbackground="#dce6f0", highlightthickness=1, bd=4)
            e.pack(fill="x", pady=(2, 10))
            fields[key] = e

        # Gender
        tk.Label(form, text="Gender", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        gender_var = tk.StringVar(value="Male")
        gender_frame = tk.Frame(form, bg=BG)
        gender_frame.pack(fill="x", pady=(2, 10))
        for g in ["Male", "Female"]:
            tk.Radiobutton(gender_frame, text=g, variable=gender_var, value=g,
                           font=FONT_SMALL, bg=BG, fg=PRIMARY,
                           activebackground=BG).pack(side="left", padx=(0, 16))

        def submit():
            name      = fields["name"].get().strip()
            age       = fields["age"].get().strip()
            contact   = fields["contact"].get().strip()
            condition = fields["condition"].get().strip()
            gender    = gender_var.get()

            if not all([name, age, contact, condition]):
                messagebox.showwarning("Missing Fields", "Please fill in all fields.", parent=win)
                return
            if not age.isdigit():
                messagebox.showwarning("Invalid Age", "Age must be a number.", parent=win)
                return

            db.add_patient(name, int(age), gender, contact, condition)
            messagebox.showinfo("Success", f"Patient '{name}' registered successfully!", parent=win)
            win.destroy()
            self.show_patients()

        btn = tk.Button(win, text="Register Patient", command=submit)
        style_button(btn)
        btn.pack(pady=16)

    # ══════════════════════════
    #  ADD APPOINTMENT MODAL
    # ══════════════════════════
    def open_add_appointment(self, patient_id=None, patient_name=None):
        win = tk.Toplevel(self)
        win.title("Book Appointment")
        win.geometry("460x500")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Book Appointment", font=FONT_TITLE,
                 fg=PRIMARY, bg=BG).pack(pady=(20, 4))
        tk.Label(win, text="Fill in appointment details", font=FONT_SMALL,
                 fg=MUTED, bg=BG).pack(pady=(0, 16))

        form = tk.Frame(win, bg=BG, padx=40)
        form.pack(fill="x")

        # Patient ID
        tk.Label(form, text="Patient ID", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        pid_entry = tk.Entry(form, font=FONT_BODY, relief="flat",
                             highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        pid_entry.pack(fill="x", pady=(2, 10))
        if patient_id:
            pid_entry.insert(0, str(patient_id))

        # Patient Name
        tk.Label(form, text="Patient Name", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        pname_entry = tk.Entry(form, font=FONT_BODY, relief="flat",
                               highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        pname_entry.pack(fill="x", pady=(2, 10))
        if patient_name:
            pname_entry.insert(0, patient_name)

        fields = {}
        for label_text, key in [("Doctor", "doctor"), ("Notes (optional)", "notes")]:
            tk.Label(form, text=label_text, font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
            e = tk.Entry(form, font=FONT_BODY, relief="flat",
                         highlightbackground="#dce6f0", highlightthickness=1, bd=4)
            e.pack(fill="x", pady=(2, 10))
            fields[key] = e

        # Date & Time
        dt_frame = tk.Frame(form, bg=BG)
        dt_frame.pack(fill="x")
        tk.Label(dt_frame, text="Date (YYYY-MM-DD)", font=FONT_SMALL, fg=PRIMARY, bg=BG).grid(row=0, column=0, sticky="w")
        tk.Label(dt_frame, text="Time (HH:MM)", font=FONT_SMALL, fg=PRIMARY, bg=BG).grid(row=0, column=1, sticky="w", padx=(16,0))
        date_entry = tk.Entry(dt_frame, font=FONT_BODY, width=16, relief="flat",
                              highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.grid(row=1, column=0, pady=(2,0))
        time_entry = tk.Entry(dt_frame, font=FONT_BODY, width=10, relief="flat",
                              highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        time_entry.insert(0, "09:00")
        time_entry.grid(row=1, column=1, pady=(2,0), padx=(16,0))

        def submit():
            pid    = pid_entry.get().strip()
            pname  = pname_entry.get().strip()
            doctor = fields["doctor"].get().strip()
            notes  = fields["notes"].get().strip()
            date   = date_entry.get().strip()
            time   = time_entry.get().strip()

            if not all([pid, pname, doctor, date, time]):
                messagebox.showwarning("Missing Fields", "Please fill in all required fields.", parent=win)
                return
            if not pid.isdigit():
                messagebox.showwarning("Invalid ID", "Patient ID must be a number.", parent=win)
                return

            all_patients = db.get_all_patients()
            patient_exists = any(str(p[0]) == pid for p in all_patients)
            if not patient_exists:
                messagebox.showwarning("Invalid Patient", f"Patient ID {pid} does not exist.", parent=win)
                return

            import re
            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            if not re.match(date_pattern, date):
                messagebox.showwarning("Invalid Date", "Use YYYY-MM-DD format (e.g., 2025-05-08)", parent=win)
                return


            db.add_appointment(int(pid), pname, doctor, date, time, notes)
            messagebox.showinfo("Success", "Appointment booked successfully!", parent=win)
            win.destroy()
            self.show_appointments()

        btn = tk.Button(win, text="Book Appointment", command=submit)
        style_button(btn, SECONDARY)
        btn.pack(pady=16)
