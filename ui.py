# ui.py — All windows and interface components

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import re

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

PANEL_BORDER = "#dce6f0"
SHADOW = "#d6e2ee"

def style_entry(entry: tk.Entry):
    entry.configure(
        font=("Segoe UI", 10),
        relief="flat",
        bg=WHITE,
        fg=PRIMARY,
        highlightbackground=PANEL_BORDER,
        highlightthickness=1,
        bd=6,
        insertbackground=PRIMARY,
    )

def surface(parent, bg=WHITE, pad=16):
    """Card-like surface with subtle border."""
    outer = tk.Frame(parent, bg=SHADOW)
    inner = tk.Frame(outer, bg=bg, padx=pad, pady=pad, highlightbackground=PANEL_BORDER, highlightthickness=1)
    inner.pack(padx=2, pady=2, fill="both", expand=True)
    return outer, inner

def setup_ttk_styles(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Treeview",
        background=WHITE,
        fieldbackground=WHITE,
        foreground=PRIMARY,
        rowheight=30,
        font=("Segoe UI", 10),
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=PRIMARY,
        foreground=WHITE,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padding=(8, 8),
    )
    style.map("Treeview", background=[("selected", SECONDARY)], foreground=[("selected", WHITE)])

    style.configure(
        "TCombobox",
        padding=6,
    )

def style_nav_button(btn: tk.Button, active: bool = False):
    base_bg = "#08304d" if active else PRIMARY
    hover_bg = "#0f4f78" if not active else "#08304d"
    btn.configure(
        font=("Segoe UI", 10, "bold" if active else "normal"),
        fg=WHITE,
        bg=base_bg,
        relief="flat",
        anchor="w",
        padx=20,
        pady=12,
        cursor="hand2",
        activebackground=hover_bg,
        activeforeground=WHITE,
        bd=0,
        highlightthickness=0,
    )

    def on_enter(_):
        if not getattr(btn, "_nav_active", False):
            btn.configure(bg=hover_bg)

    def on_leave(_):
        if not getattr(btn, "_nav_active", False):
            btn.configure(bg=PRIMARY)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)

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
        self.current_user = None
        self.active_page = None
        self.sidebar_collapsed = False
        setup_ttk_styles(self)

        # Only show the main window after successful login.
        self.withdraw()
        self._require_login()
        self._build_layout()
        self._apply_role_nav()
        self.deiconify()
        self.show_dashboard()

    def _require_login(self):
        """Block app usage until a user logs in."""
        win = tk.Toplevel(self)
        win.title("Login — StanCare")
        win.geometry("420x420")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="StanCare Login", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(22, 6))
        tk.Label(
            win,
            text="Default admin on first run:\nusername: admin   password: admin123",
            font=FONT_SMALL,
            fg=MUTED,
            bg=BG,
            justify="center",
        ).pack(pady=(0, 14))

        form = tk.Frame(win, bg=BG, padx=50)
        form.pack(fill="x")

        tk.Label(form, text="Username", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        username_var = tk.StringVar()
        username_entry = tk.Entry(
            form,
            textvariable=username_var,
        )
        style_entry(username_entry)
        username_entry.pack(fill="x", pady=(2, 12))

        tk.Label(form, text="Password", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        password_var = tk.StringVar()
        password_entry = tk.Entry(
            form,
            textvariable=password_var,
            show="•",
        )
        style_entry(password_entry)
        password_entry.pack(fill="x", pady=(2, 12))

        show_pw_var = tk.BooleanVar(value=False)
        show_pw = tk.Checkbutton(
            form,
            text="Show password",
            variable=show_pw_var,
            onvalue=True,
            offvalue=False,
            bg=BG,
            fg=PRIMARY,
            activebackground=BG,
            activeforeground=PRIMARY,
            font=("Segoe UI", 9),
            selectcolor=BG,
            cursor="hand2",
            command=lambda: password_entry.configure(show="" if show_pw_var.get() else "•"),
        )
        show_pw.pack(anchor="w", pady=(0, 4))

        status = tk.Label(win, text="", font=FONT_SMALL, fg=DANGER, bg=BG)
        status.pack(pady=(6, 0))

        def do_login():
            uname = username_var.get().strip()
            pw = password_var.get()
            if not uname or not pw:
                status.configure(text="Enter both username and password.")
                return

            user = db.authenticate(uname, pw)
            if not user:
                status.configure(text="Invalid credentials (or account disabled).")
                return

            self.current_user = user
            db.log_audit(user_id=user["id"], username=user["username"], action="LOGIN")
            win.destroy()

        def cancel():
            try:
                win.destroy()
            finally:
                self.destroy()

        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(pady=18)
        login_btn = tk.Button(btn_frame, text="Login", command=do_login)
        style_button(login_btn, SUCCESS)
        login_btn.pack(side="left", padx=(0, 10))
        exit_btn = tk.Button(btn_frame, text="Exit", command=cancel)
        style_button(exit_btn, DANGER)
        exit_btn.pack(side="left")

        password_entry.bind("<Return>", lambda e: do_login())
        username_entry.focus()

        self.wait_window(win)

    def _apply_role_nav(self):
        role = (self.current_user or {}).get("role", "")

        # Map buttons by their label text.
        btn_map = {b.cget("text"): b for b in getattr(self, "nav_buttons", [])}

        # Default: show the core modules
        allowed = {"⊞  Dashboard", "👥  Patients", "📅  Appointments", "🔍  Search"}

        # Example stricter roles
        if role == "Doctor":
            allowed = {"⊞  Dashboard", "👥  Patients", "📅  Appointments"}
        elif role == "Nurse":
            allowed = {"⊞  Dashboard", "👥  Patients"}
        elif role == "Admin":
            allowed = {"⊞  Dashboard", "👥  Patients", "📅  Appointments", "🔍  Search", "⚙  Users"}

        # Ensure admin has user management entry
        if role == "Admin" and "⚙  Users" not in btn_map:
            btn = tk.Button(
                self.sidebar,
                text="⚙  Users",
                command=self.show_users,
            )
            style_nav_button(btn, active=False)
            btn.pack(fill="x")
            self.nav_buttons.append(btn)
            btn_map["⚙  Users"] = btn

        for text, btn in btn_map.items():
            if text in allowed:
                btn.pack_configure(fill="x")
            else:
                btn.pack_forget()

        # Re-apply active highlight after role changes.
        if self.active_page:
            self._set_active_nav(self.active_page)

    def _set_active_nav(self, label_text: str):
        self.active_page = label_text
        for b in getattr(self, "nav_buttons", []):
            is_active = (b.cget("text") == label_text)
            b._nav_active = is_active
            style_nav_button(b, active=is_active)
            if not is_active:
                b.configure(bg=PRIMARY)

    def _build_layout(self):
        # ── Sidebar
        self.sidebar = tk.Frame(self, bg=PRIMARY, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        self.logo_frame = tk.Frame(self.sidebar, bg=PRIMARY, pady=20)
        self.logo_frame.pack(fill="x", padx=20)
        self.logo_icon = tk.Label(self.logo_frame, text="🏥", font=("Segoe UI", 26), bg=PRIMARY, fg=WHITE)
        self.logo_icon.pack()
        self.logo_title = tk.Label(self.logo_frame, text="StanCare", font=("Segoe UI", 15, "bold"), bg=PRIMARY, fg=WHITE)
        self.logo_title.pack()
        self.logo_subtitle = tk.Label(self.logo_frame, text="Hospital Management", font=("Segoe UI", 8), bg=PRIMARY, fg=MUTED)
        self.logo_subtitle.pack()
        tk.Frame(self.sidebar, bg=WHITE, height=1, pady=0).pack(fill="x", padx=20, pady=10)

        # Nav buttons
        self.nav_buttons = []
        self._nav_full_text = {}
        nav_items = [
            ("⊞  Dashboard",    self.show_dashboard),
            ("👥  Patients",     self.show_patients),
            ("📅  Appointments", self.show_appointments),
            ("🔍  Search",       self.show_search),
        ]
        for label_text, command in nav_items:
            btn = tk.Button(
                self.sidebar, text=label_text,
                command=command
            )
            style_nav_button(btn, active=False)
            btn.pack(fill="x")
            self.nav_buttons.append(btn)
            self._nav_full_text[btn] = label_text

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

        # Sidebar toggle
        self.sidebar_toggle_btn = tk.Button(topbar, text="☰", command=self._toggle_sidebar)
        style_button(self.sidebar_toggle_btn, WHITE, fg=PRIMARY)
        self.sidebar_toggle_btn.configure(
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=6,
            activebackground="#eef4fb",
            activeforeground=PRIMARY,
        )
        self.sidebar_toggle_btn.pack(side="left", padx=(10, 0), pady=12)

        now = datetime.now().strftime("%A, %d %B %Y")
        self.user_badge = tk.Label(topbar, text="", font=("Segoe UI", 9, "bold"), fg=PRIMARY, bg=WHITE)
        self.user_badge.pack(side="right", padx=(0, 24))
        tk.Label(topbar, text=now, font=FONT_SMALL, fg=MUTED, bg=WHITE).pack(side="right", padx=(0, 14))

        # Content frame
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=20)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def set_title(self, title):
        self.page_title.configure(text=title)

    def _toggle_sidebar(self):
        self._set_sidebar_collapsed(not self.sidebar_collapsed)

    def _set_sidebar_collapsed(self, collapsed: bool):
        self.sidebar_collapsed = collapsed
        self.sidebar.configure(width=72 if collapsed else 220)

        # Update logo
        if collapsed:
            self.logo_title.pack_forget()
            self.logo_subtitle.pack_forget()
            self.logo_frame.configure(pady=14)
        else:
            if not self.logo_title.winfo_ismapped():
                self.logo_title.pack()
            if not self.logo_subtitle.winfo_ismapped():
                self.logo_subtitle.pack()
            self.logo_frame.configure(pady=20)

        # Update nav button text (icon-only when collapsed)
        for btn in getattr(self, "nav_buttons", []):
            full = self._nav_full_text.get(btn, btn.cget("text"))
            if collapsed:
                icon = full.split("  ")[0].strip()
                btn.configure(text=f"{icon}", anchor="center", padx=0)
            else:
                btn.configure(text=full, anchor="w", padx=20)
            # Re-apply style (padding/active state)
            is_active = getattr(btn, "_nav_active", False)
            style_nav_button(btn, active=is_active)

    # ══════════════════════════
    #  DASHBOARD
    # ══════════════════════════
    def show_dashboard(self):
        self.clear_content()
        self.set_title("Dashboard")
        self._set_active_nav("⊞  Dashboard")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")
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
            card_outer, card = surface(cards_frame, bg=WHITE, pad=18)
            card_outer.grid(row=0, column=i, padx=(0, 12) if i < 3 else 0, sticky="ew")
            cards_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=("Segoe UI", 20), bg=WHITE).pack(anchor="w")
            tk.Label(card, text=value, font=("Segoe UI", 26, "bold"), fg=color, bg=WHITE).pack(anchor="w")
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
        self._set_active_nav("👥  Patients")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

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

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        widths = [40, 160, 40, 70, 110, 150, 80, 130]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center" if col != "Name" and col != "Condition" else "w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, p in enumerate(patients):
            reg_date = str(p[7])[:10] if len(p) > 7 and p[7] else ""
            status_tag = "active" if p[6] == "Active" else "discharged"
            stripe_tag = "stripe" if i % 2 == 1 else "plain"
            tree.insert("", "end", values=(p[0], p[1], p[2], p[3], p[4], p[5], p[6], reg_date),
                        tags=(status_tag, stripe_tag))
        tree.tag_configure("active",     background="#f0fff8")
        tree.tag_configure("discharged", background="#fff5f5")
        tree.tag_configure("stripe",     background="#f7fbff")

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
                    if self.current_user:
                        db.log_audit(
                            user_id=self.current_user["id"],
                            username=self.current_user["username"],
                            action="DISCHARGE_PATIENT",
                            entity_type="patients",
                            entity_id=int(pid),
                            details=f"Discharged patient '{name}'",
                        )
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
                    if self.current_user:
                        db.log_audit(
                            user_id=self.current_user["id"],
                            username=self.current_user["username"],
                            action="DELETE_PATIENT",
                            entity_type="patients",
                            entity_id=int(pid),
                            details=f"Deleted patient '{name}'",
                        )
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
        self._set_active_nav("📅  Appointments")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

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
                if self.current_user:
                    db.log_audit(
                        user_id=self.current_user["id"],
                        username=self.current_user["username"],
                        action="CANCEL_APPOINTMENT",
                        entity_type="appointments",
                        entity_id=int(aid),
                        details="Cancelled appointment",
                    )
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
        self._set_active_nav("🔍  Search")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

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
    #  USERS (ADMIN)
    # ══════════════════════════
    def show_users(self):
        self.clear_content()
        self.set_title("Users")
        self._set_active_nav("⚙  Users")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        if not self.current_user or self.current_user.get("role") != "Admin":
            messagebox.showwarning("Access Denied", "Only Admin can access user management.")
            self.show_dashboard()
            return

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Add User", command=self.open_add_user)
        style_button(add_btn, SECONDARY)
        add_btn.pack(side="left")

        cols = ("ID", "Username", "Full Name", "Role", "Active", "Created")
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = [50, 140, 190, 90, 70, 160]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="w" if col in ("Username", "Full Name") else "center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for u in db.get_users():
            uid, username, full_name, role, active, created_at = u
            tree.insert(
                "",
                "end",
                values=(uid, username, full_name or "", role, "Yes" if active else "No", created_at),
            )

        def toggle_active():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select a user.")
                return
            vals = tree.item(sel[0])["values"]
            uid = int(vals[0])
            username = vals[1]
            active_now = vals[4] == "Yes"
            if uid == self.current_user["id"]:
                messagebox.showwarning("Not allowed", "You cannot disable your own account.")
                return
            if messagebox.askyesno("Confirm", f"{'Disable' if active_now else 'Enable'} user '{username}'?"):
                db.set_user_active(uid, not active_now, changed_by_user=self.current_user)
                self.show_users()

        def reset_password():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select a user.")
                return
            vals = tree.item(sel[0])["values"]
            uid = int(vals[0])
            username = vals[1]
            self.open_reset_password(uid, username)

        btn_frame = tk.Frame(self.content, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))
        t_btn = tk.Button(btn_frame, text="Enable/Disable", command=toggle_active)
        style_button(t_btn, ACCENT, fg=PRIMARY)
        t_btn.pack(side="left", padx=(0, 10))
        r_btn = tk.Button(btn_frame, text="Reset Password", command=reset_password)
        style_button(r_btn, PRIMARY)
        r_btn.pack(side="left")

    def open_add_user(self):
        win = tk.Toplevel(self)
        win.title("Add User")
        win.geometry("460x520")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Create User", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(20, 4))
        tk.Label(win, text="Set login credentials and role", font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(0, 16))

        form = tk.Frame(win, bg=BG, padx=40)
        form.pack(fill="x")

        def add_field(title, show=None):
            tk.Label(form, text=title, font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
            e = tk.Entry(
                form,
                show=show,
            )
            style_entry(e)
            e.pack(fill="x", pady=(2, 10))
            return e

        username_e = add_field("Username")
        full_name_e = add_field("Full Name")

        tk.Label(form, text="Role", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        role_var = tk.StringVar(value="Reception")
        role_combo = ttk.Combobox(
            form,
            textvariable=role_var,
            values=["Admin", "Reception", "Nurse", "Doctor", "Lab", "Pharmacist", "Billing"],
            state="readonly",
        )
        role_combo.pack(fill="x", pady=(2, 10))

        password_e = add_field("Password", show="•")
        confirm_e = add_field("Confirm Password", show="•")

        def submit():
            username = username_e.get().strip()
            full_name = full_name_e.get().strip()
            role = role_var.get().strip()
            pw = password_e.get()
            pw2 = confirm_e.get()

            if not all([username, role, pw, pw2]):
                messagebox.showwarning("Missing Fields", "Please fill in all required fields.", parent=win)
                return
            if pw != pw2:
                messagebox.showwarning("Password", "Passwords do not match.", parent=win)
                return
            if len(pw) < 6:
                messagebox.showwarning("Password", "Password must be at least 6 characters.", parent=win)
                return
            try:
                db.create_user(username=username, password=pw, role=role, full_name=full_name, created_by_user=self.current_user)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create user.\n\n{e}", parent=win)
                return
            messagebox.showinfo("Success", f"User '{username}' created.", parent=win)
            win.destroy()
            self.show_users()

        btn = tk.Button(win, text="Create User", command=submit)
        style_button(btn, SUCCESS)
        btn.pack(pady=16)

    def open_reset_password(self, user_id: int, username: str):
        win = tk.Toplevel(self)
        win.title("Reset Password")
        win.geometry("420x360")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Reset Password", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(20, 4))
        tk.Label(win, text=f"User: {username}", font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(0, 16))

        form = tk.Frame(win, bg=BG, padx=40)
        form.pack(fill="x")

        tk.Label(form, text="New Password", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        pw1 = tk.Entry(form, show="•")
        style_entry(pw1)
        pw1.pack(fill="x", pady=(2, 10))

        tk.Label(form, text="Confirm Password", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        pw2 = tk.Entry(form, show="•")
        style_entry(pw2)
        pw2.pack(fill="x", pady=(2, 10))

        def submit():
            a = pw1.get()
            b = pw2.get()
            if not a or not b:
                messagebox.showwarning("Missing", "Enter and confirm the new password.", parent=win)
                return
            if a != b:
                messagebox.showwarning("Password", "Passwords do not match.", parent=win)
                return
            if len(a) < 6:
                messagebox.showwarning("Password", "Password must be at least 6 characters.", parent=win)
                return
            try:
                db.set_user_password(user_id, a, changed_by_user=self.current_user)
            except Exception as e:
                messagebox.showerror("Error", f"Could not reset password.\n\n{e}", parent=win)
                return
            messagebox.showinfo("Success", "Password reset.", parent=win)
            win.destroy()

        btn = tk.Button(win, text="Reset Password", command=submit)
        style_button(btn, ACCENT, fg=PRIMARY)
        btn.pack(pady=16)

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
            e = tk.Entry(form)
            style_entry(e)
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

            pid = db.add_patient(name, int(age), gender, contact, condition)
            if self.current_user:
                db.log_audit(
                    user_id=self.current_user["id"],
                    username=self.current_user["username"],
                    action="ADD_PATIENT",
                    entity_type="patients",
                    entity_id=int(pid),
                    details=f"Registered patient '{name}'",
                )
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
        style_entry(pid_entry)
        pid_entry.pack(fill="x", pady=(2, 10))
        if patient_id:
            pid_entry.insert(0, str(patient_id))

        # Patient Name (read-only, derived from DB)
        tk.Label(form, text="Patient Name", font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
        pname_var = tk.StringVar(value="")
        pname_entry = tk.Entry(form, textvariable=pname_var)
        style_entry(pname_entry)
        pname_entry.pack(fill="x", pady=(2, 10))
        pname_entry.configure(state="readonly")
        if patient_name:
            pname_var.set(patient_name)

        fields = {}
        for label_text, key in [("Doctor", "doctor"), ("Notes (optional)", "notes")]:
            tk.Label(form, text=label_text, font=FONT_SMALL, fg=PRIMARY, bg=BG, anchor="w").pack(fill="x")
            e = tk.Entry(form)
            style_entry(e)
            e.pack(fill="x", pady=(2, 10))
            fields[key] = e

        # Date & Time
        dt_frame = tk.Frame(form, bg=BG)
        dt_frame.pack(fill="x")
        tk.Label(dt_frame, text="Date (YYYY-MM-DD)", font=FONT_SMALL, fg=PRIMARY, bg=BG).grid(row=0, column=0, sticky="w")
        tk.Label(dt_frame, text="Time (HH:MM)", font=FONT_SMALL, fg=PRIMARY, bg=BG).grid(row=0, column=1, sticky="w", padx=(16,0))
        date_entry = tk.Entry(dt_frame, font=FONT_BODY, width=16, relief="flat",
                              highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        style_entry(date_entry)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.grid(row=1, column=0, pady=(2,0))
        time_entry = tk.Entry(dt_frame, font=FONT_BODY, width=10, relief="flat",
                              highlightbackground="#dce6f0", highlightthickness=1, bd=4)
        style_entry(time_entry)
        time_entry.insert(0, "09:00")
        time_entry.grid(row=1, column=1, pady=(2,0), padx=(16,0))

        def refresh_patient_name(*_):
            pid = pid_entry.get().strip()
            if not pid.isdigit():
                pname_var.set("")
                return
            name = db.get_patient_name(int(pid))
            pname_var.set(name or "")

        refresh_patient_name()
        pid_entry.bind("<KeyRelease>", refresh_patient_name)

        def submit():
            pid    = pid_entry.get().strip()
            doctor = fields["doctor"].get().strip()
            notes  = fields["notes"].get().strip()
            date   = date_entry.get().strip()
            time   = time_entry.get().strip()

            if not all([pid, doctor, date, time]):
                messagebox.showwarning("Missing Fields", "Please fill in all required fields.", parent=win)
                return
            if not pid.isdigit():
                messagebox.showwarning("Invalid ID", "Patient ID must be a number.", parent=win)
                return
            pid_i = int(pid)

            if not db.patient_exists(pid_i):
                messagebox.showwarning("Invalid Patient", f"Patient ID {pid} does not exist.", parent=win)
                return

            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                messagebox.showwarning("Invalid Date", "Use YYYY-MM-DD format (e.g., 2025-05-08)", parent=win)
                return
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                messagebox.showwarning("Invalid Date", "That date is not valid.", parent=win)
                return

            if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time):
                messagebox.showwarning("Invalid Time", "Use HH:MM (24-hour) format (e.g., 09:30)", parent=win)
                return

            try:
                db.add_appointment(pid_i, doctor, date, time, notes)
            except Exception as e:
                messagebox.showerror("Database Error", f"Could not book appointment.\n\n{e}", parent=win)
                return
            if self.current_user:
                pname = db.get_patient_name(pid_i) or ""
                db.log_audit(
                    user_id=self.current_user["id"],
                    username=self.current_user["username"],
                    action="BOOK_APPOINTMENT",
                    entity_type="appointments",
                    entity_id=None,
                    details=f"Booked for patient_id={pid_i} '{pname}' with Dr '{doctor}' on {date} {time}",
                )

            messagebox.showinfo("Success", "Appointment booked successfully!", parent=win)
            win.destroy()
            self.show_appointments()

        btn = tk.Button(win, text="Book Appointment", command=submit)
        style_button(btn, SECONDARY)
        btn.pack(pady=16)
