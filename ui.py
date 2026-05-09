# ui.py — All windows and interface components

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database as db
import re
import os
import shutil
import csv
import sys

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
    # Make heading hover/active readable (some themes flip colors on hover).
    style.map(
        "Treeview.Heading",
        background=[
            ("active", "#e8f1fb"),
            ("pressed", "#d7e8fb"),
        ],
        foreground=[
            ("active", PRIMARY),
            ("pressed", PRIMARY),
        ],
    )
    # Ensure good contrast on both hover (active) and selection.
    style.map(
        "Treeview",
        background=[
            ("selected", SECONDARY),
            ("active", "#e8f1fb"),
        ],
        foreground=[
            ("selected", WHITE),
            ("active", PRIMARY),
        ],
    )

    style.configure(
        "TCombobox",
        padding=6,
    )

    # Scrollbars (slimmer + modern colors)
    style.configure(
        "TScrollbar",
        gripcount=0,
        bordercolor=PANEL_BORDER,
        troughcolor="#eef4fb",
        background="#c7d9ee",
        darkcolor="#c7d9ee",
        lightcolor="#c7d9ee",
        arrowcolor=PRIMARY,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "TScrollbar",
        background=[
            ("active", "#b3cbe7"),
            ("pressed", "#9fbbe0"),
        ],
        arrowcolor=[
            ("active", PRIMARY),
            ("pressed", PRIMARY),
        ],
    )

    style.configure("Vertical.TScrollbar", arrowsize=12, width=10)
    style.configure("Horizontal.TScrollbar", arrowsize=12, width=10)

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
        """Landing → role-specific login until success or app exit."""
        while True:
            mode = self._show_role_selector()
            if mode == "__EXIT__":
                self.destroy()
                sys.exit(0)
            if self._show_login_screen(mode):
                return

    def _show_role_selector(self):
        """Landing page: Doctor, Nurse, Lab, Pharmacy, Reception + administrator link."""
        result = {"mode": None}
        win = tk.Toplevel(self)
        win.title("StanCare — Welcome")
        win.geometry("980x760")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(860, 640)
        win.grab_set()

        def on_role_win_close():
            if result["mode"] is None:
                result["mode"] = "__EXIT__"
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_role_win_close)

        FOOTER_PANEL = "#e9f1f8"

        def choose(m):
            result["mode"] = m
            win.destroy()

        # Footer packed first so it stays visible; body fills remaining height (works better maximized).
        footer_bar = tk.Frame(win, bg=FOOTER_PANEL)
        footer_bar.pack(side="bottom", fill="x")
        tk.Frame(footer_bar, bg=PANEL_BORDER, height=1).pack(fill="x", side="top")
        footer_inner = tk.Frame(footer_bar, bg=FOOTER_PANEL)
        footer_inner.pack(fill="x", padx=32, pady=(14, 16))

        foot_left = tk.Frame(footer_inner, bg=FOOTER_PANEL)
        foot_left.pack(side="left", fill="y")
        tk.Label(
            foot_left,
            text="© 2026 StanCare",
            font=("Segoe UI", 10, "bold"),
            fg=PRIMARY,
            bg=FOOTER_PANEL,
        ).pack(anchor="w")
        tk.Label(
            foot_left,
            text="Hospital Management System · Close this window to exit",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=FOOTER_PANEL,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        foot_right = tk.Frame(footer_inner, bg=FOOTER_PANEL)
        foot_right.pack(side="right")
        tk.Label(
            foot_right,
            text="Administrators",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=FOOTER_PANEL,
        ).pack(side="left", padx=(0, 12))
        adm_btn = tk.Button(foot_right, text="Administrator sign-in", command=lambda: choose("Administrator"))
        style_button(adm_btn, WHITE, fg=PRIMARY)
        adm_btn.configure(font=("Segoe UI", 9, "bold"), padx=16, pady=8, activebackground="#dfeaf7")

        _adm_idle_bg, _adm_idle_fg = WHITE, PRIMARY

        def _adm_enter(_):
            adm_btn.configure(bg="#e4f0fb", fg="#08304d", cursor="hand2")

        def _adm_leave(_):
            adm_btn.configure(bg=_adm_idle_bg, fg=_adm_idle_fg, cursor="hand2")

        adm_btn.bind("<Enter>", _adm_enter)
        adm_btn.bind("<Leave>", _adm_leave)

        header = tk.Frame(win, bg=PRIMARY)
        header.pack(side="top", fill="x")
        header_inner = tk.Frame(header, bg=PRIMARY)
        header_inner.pack(fill="x", padx=28, pady=(18, 22))

        logo_row = tk.Frame(header_inner, bg=PRIMARY)
        logo_row.pack(fill="x")

        badge = tk.Frame(logo_row, bg="#08304d", width=56, height=56)
        badge.pack(side="left", padx=(0, 18))
        badge.pack_propagate(False)
        tk.Label(badge, text="\U0001f3e5", font=("Segoe UI", 26), bg="#08304d", fg=WHITE).place(relx=0.5, rely=0.5, anchor="center")

        brand_col = tk.Frame(logo_row, bg=PRIMARY)
        brand_col.pack(side="left", fill="y")
        tk.Label(brand_col, text="StanCare", font=("Segoe UI", 26, "bold"), fg=WHITE, bg=PRIMARY).pack(anchor="w")
        tk.Label(
            brand_col,
            text="Hospital Management System",
            font=("Segoe UI", 11),
            fg="#c5d6e8",
            bg=PRIMARY,
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True, padx=36, pady=(22, 16))

        tk.Label(
            body,
            text="How would you like to sign in?",
            font=("Segoe UI", 17, "bold"),
            fg=PRIMARY,
            bg=BG,
        ).pack(anchor="w")
        subtitle_lbl = tk.Label(
            body,
            text="Pick your role — we'll open the correct login screen for you.",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BG,
            wraplength=880,
            justify="left",
        )
        subtitle_lbl.pack(anchor="w", pady=(6, 14))

        def _reflow_subtitle(_event=None):
            try:
                w = max(body.winfo_width() - 8, 280)
                subtitle_lbl.configure(wraplength=w)
            except tk.TclError:
                pass

        body.bind("<Configure>", _reflow_subtitle)

        tiles_wrap = tk.Frame(body, bg=BG)
        tiles_wrap.pack(fill="both", expand=True)
        for col in range(3):
            tiles_wrap.grid_columnconfigure(col, weight=1)
        tiles_wrap.grid_rowconfigure(0, weight=1)
        tiles_wrap.grid_rowconfigure(1, weight=1)

        tiles_spec = [
            ("Doctor", "\U0001fa7a", "Doctor", "Doctor ID + password — clinical workspace.", 0, 0, 1),
            ("Nurse", "\U0001f489", "Nurse", "Nurse ID + password — vitals and patient care.", 0, 1, 1),
            ("Lab", "\U0001f9ea", "Laboratory", "Lab ID + password — orders and results.", 0, 2, 1),
            ("Pharmacist", "\U0001f48a", "Pharmacy", "Username + password — pharmacy & inventory.", 1, 0, 1),
            ("Reception", "\U0001f4c5", "Reception", "Username + password — appointments & front desk.", 1, 1, 1),
        ]

        TILE_IDLE_OUTER = SHADOW
        TILE_IDLE_INNER = WHITE
        TILE_HOVER_OUTER = "#b7cce3"
        TILE_HOVER_INNER = "#f3f9ff"
        TILE_HOVER_BORDER = SECONDARY

        def build_tile(mode_key, icon, title, blurb, row, col, colspan):
            cell = tk.Frame(tiles_wrap, bg=BG, cursor="hand2")
            cell.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
            outer, inner = surface(cell, bg=TILE_IDLE_INNER, pad=20)
            outer.pack(fill="both", expand=True)
            outer.configure(bg=TILE_IDLE_OUTER)

            icon_lbl = tk.Label(inner, text=icon, font=("Segoe UI", 28), bg=TILE_IDLE_INNER)
            icon_lbl.pack(anchor="w")
            title_lbl = tk.Label(inner, text=title, font=("Segoe UI", 13, "bold"), fg=PRIMARY, bg=TILE_IDLE_INNER)
            title_lbl.pack(anchor="w", pady=(8, 4))
            blurb_lbl = tk.Label(
                inner,
                text=blurb,
                font=("Segoe UI", 10),
                fg=MUTED,
                bg=TILE_IDLE_INNER,
                wraplength=300 if colspan == 1 else 280,
                justify="left",
            )
            blurb_lbl.pack(anchor="w")
            hint_lbl = tk.Label(inner, text="Click to continue →", font=("Segoe UI", 9, "bold"), fg=SECONDARY, bg=TILE_IDLE_INNER)
            hint_lbl.pack(anchor="w", pady=(14, 0))

            def on_pick(event=None, m=mode_key):
                choose(m)

            def tile_hover_on(_event=None):
                outer.configure(bg=TILE_HOVER_OUTER)
                inner.configure(bg=TILE_HOVER_INNER, highlightbackground=TILE_HOVER_BORDER)
                for lbl in (icon_lbl, title_lbl, blurb_lbl, hint_lbl):
                    lbl.configure(bg=TILE_HOVER_INNER)
                hint_lbl.configure(fg=PRIMARY)

            def tile_hover_off(_event=None):
                outer.configure(bg=TILE_IDLE_OUTER)
                inner.configure(bg=TILE_IDLE_INNER, highlightbackground=PANEL_BORDER)
                for lbl in (icon_lbl, title_lbl, blurb_lbl, hint_lbl):
                    lbl.configure(bg=TILE_IDLE_INNER)
                hint_lbl.configure(fg=SECONDARY)

            cell.bind("<Enter>", tile_hover_on)
            cell.bind("<Leave>", tile_hover_off)

            for w in (outer, inner, icon_lbl, title_lbl, blurb_lbl, hint_lbl):
                w.bind("<Button-1>", on_pick)
                w.configure(cursor="hand2")

        for spec in tiles_spec:
            build_tile(*spec)

        win.after(100, _reflow_subtitle)

        self.wait_window(win)
        return result["mode"]

    def _show_login_screen(self, mode: str):
        """Focused login for one role. Returns True if logged in, False if Back (returns to landing)."""
        titles = {
            "Pharmacist": "Pharmacy sign-in",
            "Reception": "Reception sign-in",
            "Administrator": "Administrator sign-in",
            "Doctor": "Doctor sign-in",
            "Nurse": "Nurse sign-in",
            "Lab": "Laboratory sign-in",
        }
        subtitles = {
            "Pharmacist": "Pharmacy username and password (assigned by administration).",
            "Reception": "Reception username and password (assigned by administration).",
            "Administrator": "Hospital administrator accounts only.",
            "Doctor": "Use your Doctor ID and password.",
            "Nurse": "Use your Nurse ID and password.",
            "Lab": "Use your Lab ID and password.",
        }
        is_doctor = mode == "Doctor"
        outcome = {"ok": False}
        win = tk.Toplevel(self)
        win.title(f"{titles.get(mode, 'Sign in')} — StanCare")
        win.geometry("580x780" if is_doctor else "520x600")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        def go_back():
            outcome["ok"] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", go_back)

        card_outer = None
        card = None

        if is_doctor:
            header = tk.Frame(win, bg=PRIMARY)
            header.pack(fill="x")
            nav_row = tk.Frame(header, bg=PRIMARY)
            nav_row.pack(fill="x", padx=(20, 22), pady=(14, 0))
            back_btn = tk.Button(
                nav_row,
                text="←  Back to role selection",
                command=go_back,
                bg=PRIMARY,
                fg="#d7ebff",
                font=("Segoe UI", 10),
                relief="flat",
                cursor="hand2",
                padx=2,
                pady=6,
                activebackground="#08304d",
                activeforeground=WHITE,
                bd=0,
                highlightthickness=0,
            )
            back_btn.pack(side="left")

            hero = tk.Frame(header, bg=PRIMARY)
            hero.pack(fill="x", padx=22, pady=(12, 24))
            tk.Label(hero, text="\U0001fa7a", font=("Segoe UI", 38), bg=PRIMARY).pack(side="left", padx=(0, 16))
            hero_txt = tk.Frame(hero, bg=PRIMARY)
            hero_txt.pack(side="left", fill="y")
            tk.Label(hero_txt, text="Doctor portal", font=("Segoe UI", 23, "bold"), fg=WHITE, bg=PRIMARY).pack(anchor="w")
            tk.Label(
                hero_txt,
                text="Clinical workspace · sign in with your credentials",
                font=("Segoe UI", 10),
                fg="#b3cce8",
                bg=PRIMARY,
            ).pack(anchor="w", pady=(6, 0))

            body = tk.Frame(win, bg=BG)
            body.pack(fill="both", expand=True)
            card_outer, card = surface(body, bg=WHITE, pad=26)
            card_outer.pack(fill="both", expand=True, padx=26, pady=(14, 22))
        else:
            top = tk.Frame(win, bg=BG)
            top.pack(fill="x", padx=22, pady=(16, 8))
            back_lbl = "←  Back to welcome"
            back_btn = tk.Button(top, text=back_lbl, command=go_back)
            style_button(back_btn, WHITE, fg=PRIMARY)
            back_btn.configure(activebackground="#eef4fb", activeforeground=PRIMARY, padx=12, pady=6)
            back_btn.pack(side="left")

            tk.Label(win, text=titles.get(mode, "Sign in"), font=("Segoe UI", 20, "bold"), fg=PRIMARY, bg=BG).pack(pady=(8, 4))
            tk.Label(win, text=subtitles.get(mode, ""), font=("Segoe UI", 10), fg=MUTED, bg=BG).pack(pady=(0, 14))

            card_outer, card = surface(win, bg=WHITE, pad=22)
            card_outer.pack(fill="both", expand=True, padx=26, pady=(0, 22))

        staff_frame = tk.Frame(card, bg=WHITE)
        id_frame = tk.Frame(card, bg=WHITE)

        tk.Label(staff_frame, text="Username", font=("Segoe UI", 9, "bold"), fg=PRIMARY, bg=WHITE, anchor="w").pack(fill="x")
        username_var = tk.StringVar()
        username_entry = tk.Entry(staff_frame, textvariable=username_var)
        style_entry(username_entry)
        username_entry.pack(fill="x", pady=(6, 14))

        if is_doctor:
            tk.Label(id_frame, text="Doctor ID", font=("Segoe UI", 10, "bold"), fg=PRIMARY, bg=WHITE, anchor="w").pack(fill="x")
            tk.Label(
                id_frame,
                text="Numeric ID assigned by administration (same ID you use at the desk).",
                font=("Segoe UI", 9),
                fg=MUTED,
                bg=WHITE,
                anchor="w",
                wraplength=480,
                justify="left",
            ).pack(fill="x", pady=(2, 10))
        else:
            tk.Label(id_frame, text="ID", font=("Segoe UI", 9, "bold"), fg=PRIMARY, bg=WHITE, anchor="w").pack(fill="x")

        login_id_var = tk.StringVar()
        login_id_entry = tk.Entry(id_frame, textvariable=login_id_var)
        style_entry(login_id_entry)
        login_id_entry.pack(fill="x", pady=(0, 14) if is_doctor else (6, 14))

        if mode in ("Pharmacist", "Reception", "Administrator"):
            staff_frame.pack(fill="x")
            if mode == "Administrator":
                tk.Label(
                    card,
                    text="First-time setup: username admin / password admin123",
                    font=("Segoe UI", 9),
                    fg=MUTED,
                    bg=WHITE,
                    wraplength=440,
                    justify="left",
                ).pack(anchor="w", pady=(0, 16))
            username_entry.focus()
        else:
            id_frame.pack(fill="x")
            login_id_entry.focus()

        password_var = tk.StringVar()
        tk.Label(
            card,
            text="Password",
            font=("Segoe UI", 10, "bold") if is_doctor else ("Segoe UI", 9, "bold"),
            fg=PRIMARY,
            bg=WHITE,
        ).pack(fill="x")
        password_entry = tk.Entry(card, textvariable=password_var, show="•")
        style_entry(password_entry)
        password_entry.pack(fill="x", pady=(6, 10))

        show_pw_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            card,
            text="Show password",
            variable=show_pw_var,
            onvalue=True,
            offvalue=False,
            bg=WHITE,
            fg=PRIMARY,
            activebackground=WHITE,
            activeforeground=PRIMARY,
            font=("Segoe UI", 9),
            selectcolor=WHITE,
            cursor="hand2",
            command=lambda: password_entry.configure(show="" if show_pw_var.get() else "•"),
        ).pack(anchor="w", pady=(0, 10))

        def open_doctor_reset_request():
            dlg = tk.Toplevel(win)
            dlg.title("Password reset — Doctor")
            dlg.geometry("480x380")
            dlg.configure(bg=BG)
            dlg.transient(win)
            dlg.grab_set()
            dlg.resizable(False, False)

            tk.Label(
                dlg,
                text="Request password reset",
                font=("Segoe UI", 15, "bold"),
                fg=PRIMARY,
                bg=BG,
            ).pack(anchor="w", padx=24, pady=(22, 8))
            tk.Label(
                dlg,
                text="Your request is logged for administrators. They will verify your identity and issue a new password. "
                "Use the Doctor ID from your badge or HR paperwork.",
                font=("Segoe UI", 10),
                fg=MUTED,
                bg=BG,
                wraplength=430,
                justify="left",
            ).pack(anchor="w", padx=24, pady=(0, 16))

            tk.Label(dlg, text="Doctor ID", font=("Segoe UI", 9, "bold"), fg=PRIMARY, bg=BG).pack(anchor="w", padx=24)
            req_id_var = tk.StringVar(value=login_id_var.get().strip())
            req_id_entry = tk.Entry(dlg, textvariable=req_id_var)
            style_entry(req_id_entry)
            req_id_entry.pack(fill="x", padx=24, pady=(6, 12))

            tk.Label(dlg, text="Optional note for IT / admin (phone extension, department)", font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(
                anchor="w", padx=24
            )
            note_box = tk.Text(dlg, height=5, font=("Segoe UI", 10), fg=PRIMARY, bg=WHITE, relief="flat", highlightbackground=PANEL_BORDER, highlightthickness=1, padx=8, pady=8)
            note_box.pack(fill="x", padx=24, pady=(6, 18))

            def submit_reset_req():
                lid = req_id_var.get().strip()
                if not lid.isdigit():
                    messagebox.showwarning("Doctor ID", "Enter your numeric Doctor ID.", parent=dlg)
                    return
                note = note_box.get("1.0", tk.END).strip()
                try:
                    db.record_login_password_reset_request("Doctor", int(lid), note)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not submit request.\n\n{e}", parent=dlg)
                    return
                messagebox.showinfo(
                    "Submitted",
                    "Your reset request has been recorded in the audit log. "
                    "Please follow up with administration if you need urgent access.",
                    parent=dlg,
                )
                dlg.destroy()

            bf = tk.Frame(dlg, bg=BG)
            bf.pack(fill="x", padx=24, pady=(0, 22))
            sb = tk.Button(bf, text="Submit request", command=submit_reset_req)
            style_button(sb, SECONDARY)
            sb.pack(side="left", padx=(0, 10))
            cb = tk.Button(bf, text="Cancel", command=dlg.destroy)
            style_button(cb, WHITE, fg=PRIMARY)
            cb.configure(activebackground="#eef4fb")
            cb.pack(side="left")

            dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        if is_doctor:
            reset_hint = tk.Frame(card, bg=WHITE)
            reset_hint.pack(fill="x", pady=(0, 8))
            reset_link = tk.Label(
                reset_hint,
                text="Forgot password? Request a reset",
                font=("Segoe UI", 10, "underline"),
                fg=SECONDARY,
                bg=WHITE,
                cursor="hand2",
            )
            reset_link.pack(anchor="w")
            reset_link.bind("<Button-1>", lambda _e: open_doctor_reset_request())

        status = tk.Label(card, text="", font=("Segoe UI", 9), fg=DANGER, bg=WHITE)
        status.pack(anchor="w", pady=(0, 10))

        def do_login():
            pw = password_var.get()
            if not pw:
                status.configure(text="Enter your password.")
                return

            if mode in ("Pharmacist", "Reception", "Administrator"):
                uname = username_var.get().strip()
                if not uname:
                    status.configure(text="Enter your username.")
                    return
                user = db.authenticate(uname, pw)
                if not user:
                    status.configure(text="Invalid credentials (or account disabled).")
                    return
                if mode == "Administrator":
                    if user.get("role") != "Admin":
                        status.configure(text="This entrance is for administrator accounts only.")
                        return
                elif mode == "Pharmacist":
                    if user.get("role") != "Pharmacist":
                        status.configure(text="This entrance is for pharmacy staff accounts only.")
                        return
                elif mode == "Reception":
                    if user.get("role") != "Reception":
                        status.configure(text="This entrance is for reception accounts only.")
                        return
            else:
                lid = login_id_var.get().strip()
                if not lid.isdigit():
                    status.configure(text="Enter a numeric ID.")
                    return
                role_map = {"Doctor": "Doctor", "Nurse": "Nurse", "Lab": "Lab"}
                user = db.authenticate_by_login_id(role_map[mode], int(lid), pw)
                if not user:
                    status.configure(text="Invalid credentials (or account disabled).")
                    return

            self.current_user = user
            db.log_audit(user_id=user["id"], username=user["username"], action="LOGIN")
            outcome["ok"] = True
            win.destroy()

        def cancel_app():
            win.destroy()
            self.destroy()
            sys.exit(0)

        btn_frame = tk.Frame(card, bg=WHITE)
        btn_frame.pack(fill="x", pady=(12, 0))
        login_btn = tk.Button(btn_frame, text="Sign in to portal" if is_doctor else "Sign in", command=do_login)
        style_button(login_btn, SUCCESS)
        login_btn.pack(side="left", padx=(0, 10))
        exit_btn = tk.Button(btn_frame, text="Quit app", command=cancel_app)
        style_button(exit_btn, DANGER)
        exit_btn.pack(side="left")

        if mode not in ("Pharmacist", "Reception", "Administrator"):
            login_id_entry.bind("<Return>", lambda _e: password_entry.focus())
        else:
            username_entry.bind("<Return>", lambda _e: password_entry.focus())
        password_entry.bind("<Return>", lambda _e: do_login())

        self.wait_window(win)
        return outcome["ok"]

    def _apply_role_nav(self):
        role = (self.current_user or {}).get("role", "")

        # Map buttons by their label text.
        btn_map = {b.cget("text"): b for b in getattr(self, "nav_buttons", [])}

        # Default: minimal (lock down by role)
        allowed = {"⊞  Dashboard"}

        # Example stricter roles
        if role == "Doctor":
            allowed = {"⊞  Dashboard", "👥  Patients"}
        elif role == "Nurse":
            allowed = {"⊞  Dashboard", "🩺  Vitals"}
        elif role == "Lab":
            allowed = {"⊞  Dashboard", "🧪  Lab Upload"}
        elif role == "Pharmacist":
            allowed = {"⊞  Dashboard", "💊  Pharmacy"}
        elif role == "Reception":
            allowed = {"⊞  Dashboard", "📅  Appointments", "🔍  Search"}
        elif role == "Billing":
            allowed = {"⊞  Dashboard", "💳  Billing"}
        elif role == "Admin":
            # Admin manages operations but does NOT access patient list per your requirement.
            allowed = {
                "⊞  Dashboard",
                "👨‍⚕️  Doctors",
                "📇  Staff registry",
                "💳  Billing",
                "💊  Pharmacy",
                "🧪  Lab",
                "📜  Audit Log",
                "💾  Backups/Exports",
            }
        else:
            # Other staff roles can be added later; keep conservative for now.
            allowed = {"⊞  Dashboard"}

        # Ensure role-specific nav entries exist
        if role == "Nurse" and "🩺  Vitals" not in btn_map:
            btn = tk.Button(self.sidebar, text="🩺  Vitals", command=self.show_vitals_station)
            style_nav_button(btn, active=False)
            if hasattr(self, "sidebar_spacer"):
                btn.pack(fill="x", before=self.sidebar_spacer)
            else:
                btn.pack(fill="x")
            self.nav_buttons.append(btn)
            btn_map["🩺  Vitals"] = btn
            if hasattr(self, "_nav_full_text"):
                self._nav_full_text[btn] = "🩺  Vitals"

        if role == "Lab" and "🧪  Lab Upload" not in btn_map:
            btn = tk.Button(self.sidebar, text="🧪  Lab Upload", command=self.show_lab_upload)
            style_nav_button(btn, active=False)
            if hasattr(self, "sidebar_spacer"):
                btn.pack(fill="x", before=self.sidebar_spacer)
            else:
                btn.pack(fill="x")
            self.nav_buttons.append(btn)
            btn_map["🧪  Lab Upload"] = btn
            if hasattr(self, "_nav_full_text"):
                self._nav_full_text[btn] = "🧪  Lab Upload"

        # Ensure admin has user management entry
        if role == "Admin":
            admin_entries = [
                ("👨‍⚕️  Doctors", self.show_doctors),
                ("📇  Staff registry", self.show_staff_registry),
                ("💳  Billing", self.show_billing),
                ("💊  Pharmacy", self.show_pharmacy),
                ("🧪  Lab", self.show_lab),
                ("📜  Audit Log", self.show_audit_log),
                ("💾  Backups/Exports", self.show_backups_exports),
            ]
            for label_text, command in admin_entries:
                if label_text not in btn_map:
                    btn = tk.Button(self.sidebar, text=label_text, command=command)
                    style_nav_button(btn, active=False)
                    if hasattr(self, "sidebar_spacer"):
                        btn.pack(fill="x", before=self.sidebar_spacer)
                    else:
                        btn.pack(fill="x")
                    self.nav_buttons.append(btn)
                    btn_map[label_text] = btn
                    if hasattr(self, "_nav_full_text"):
                        self._nav_full_text[btn] = label_text

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

        # Spacer + Footer pinned to bottom
        self.sidebar_spacer = tk.Frame(self.sidebar, bg=PRIMARY)
        self.sidebar_spacer.pack(fill="both", expand=True)

        footer = tk.Frame(self.sidebar, bg=PRIMARY)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, text="© 2026 StanCare",
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
        self.logout_btn = tk.Button(topbar, text="Logout", command=self.logout)
        style_button(self.logout_btn, WHITE, fg=PRIMARY)
        self.logout_btn.configure(activebackground="#eef4fb", activeforeground=PRIMARY)
        self.logout_btn.pack(side="right", padx=(0, 10), pady=12)
        tk.Label(topbar, text=now, font=FONT_SMALL, fg=MUTED, bg=WHITE).pack(side="right", padx=(0, 14))

        # Content frame
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=20)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def set_title(self, title):
        self.page_title.configure(text=title)

    # ══════════════════════════
    #  BACKUP / EXPORT
    # ══════════════════════════
    def backup_database(self):
        try:
            src = os.path.join(os.getcwd(), db.DB_NAME)
            if not os.path.exists(src):
                src = db.DB_NAME
            if not os.path.exists(src):
                messagebox.showerror("Backup", f"Database file not found:\n{db.DB_NAME}")
                return
            backups_dir = os.path.join(os.getcwd(), "backups")
            os.makedirs(backups_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(backups_dir, f"hospital_backup_{ts}.db")
            shutil.copy2(src, dest)
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "BACKUP_DB", "db", None, f"Created backup: {dest}")
            messagebox.showinfo("Backup", f"Backup created:\n{dest}")
        except Exception as e:
            messagebox.showerror("Backup", f"Backup failed.\n\n{e}")

    def open_export_menu(self):
        win = tk.Toplevel(self)
        win.title("Export CSV")
        win.geometry("420x320")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Export CSV", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        tk.Label(win, text="Files are saved to the `exports` folder.", font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(0, 12))

        outer, frame = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        def btn(txt, fn):
            b = tk.Button(frame, text=txt, command=lambda: (fn(), win.destroy()))
            style_button(b, SECONDARY)
            b.pack(fill="x", pady=(0, 10))

        btn("Export Patients", self.export_patients_csv)
        btn("Export Appointments", self.export_appointments_csv)
        btn("Export Invoices", self.export_invoices_csv)
        btn("Export Inventory", self.export_inventory_csv)

    def _export_rows(self, filename: str, headers, rows):
        exports_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        path = os.path.join(exports_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        return path

    def export_patients_csv(self):
        rows = db.get_all_patients()
        path = self._export_rows(
            f"patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            ["id", "name", "age", "gender", "contact", "condition", "status", "registered"],
            rows,
        )
        if self.current_user:
            db.log_audit(self.current_user["id"], self.current_user["username"], "EXPORT_CSV", "patients", None, path)
        messagebox.showinfo("Export", f"Saved:\n{path}")

    def export_appointments_csv(self):
        rows = db.get_all_appointments()
        path = self._export_rows(
            f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            ["id", "patient_id", "patient_name", "doctor", "date", "time", "notes", "status"],
            rows,
        )
        if self.current_user:
            db.log_audit(self.current_user["id"], self.current_user["username"], "EXPORT_CSV", "appointments", None, path)
        messagebox.showinfo("Export", f"Saved:\n{path}")

    def export_invoices_csv(self):
        rows = db.get_all_invoices()
        path = self._export_rows(
            f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            ["invoice_id", "patient_name", "status", "created_at", "total", "paid"],
            rows,
        )
        if self.current_user:
            db.log_audit(self.current_user["id"], self.current_user["username"], "EXPORT_CSV", "invoices", None, path)
        messagebox.showinfo("Export", f"Saved:\n{path}")

    def export_inventory_csv(self):
        rows = db.get_inventory_items()
        path = self._export_rows(
            f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            ["id", "sku", "name", "category", "unit", "quantity", "reorder_level", "updated_at"],
            rows,
        )
        if self.current_user:
            db.log_audit(self.current_user["id"], self.current_user["username"], "EXPORT_CSV", "inventory", None, path)
        messagebox.showinfo("Export", f"Saved:\n{path}")

    def _toggle_sidebar(self):
        self._set_sidebar_collapsed(not self.sidebar_collapsed)

    def logout(self):
        """Log out current user and return to login page."""
        if self.current_user:
            try:
                db.log_audit(self.current_user["id"], self.current_user["username"], "LOGOUT")
            except Exception:
                pass
        self.current_user = None
        self.active_page = None
        # Tear down UI and restart login + layout
        self.withdraw()
        for w in self.winfo_children():
            w.destroy()
        self._require_login()
        self._build_layout()
        self._apply_role_nav()
        self.deiconify()
        self.show_dashboard()

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
        role = (self.current_user or {}).get("role", "")
        stats = db.get_stats()

        def bind_click_recursive(widget, callback):
            widget.bind("<Button-1>", lambda e: callback())
            for child in widget.winfo_children():
                bind_click_recursive(child, callback)

        # Stat cards
        cards_frame = tk.Frame(self.content, bg=BG)
        cards_frame.pack(fill="x", pady=(0, 20))

        if role == "Admin":
            kpi = db.get_admin_kpis()
            card_data = [
                ("Patients registered", str(kpi["patients_registered"]), PRIMARY, "👥", None),
                ("Appointments today", str(kpi["appointments_today"]), ACCENT, "📅", None),
                ("Unpaid invoices", str(kpi["unpaid_invoice_count"]), DANGER, "💳", self.show_billing),
                ("Low-stock SKUs", str(kpi["low_stock_skus"]), SECONDARY, "💊", self.show_pharmacy),
            ]
        elif role == "Doctor":
            card_data = [
                ("Total Patients",     str(stats["total"]),               PRIMARY,  "👥", lambda: self.show_patients("All")),
                ("Active Patients",    str(stats["active"]),              SUCCESS,  "✅", lambda: self.show_patients("Active")),
                ("Discharged",         str(stats["discharged"]),          MUTED,    "🏠", lambda: self.show_patients("Discharged")),
                ("Appointments Today", str(stats["today_appointments"]),  ACCENT,   "📅", self.show_appointments),
            ]
        else:
            card_data = [
                ("Patients registered", str(stats["total"]), PRIMARY, "👥", None),
                ("Active patients", str(stats["active"]), SUCCESS, "✅", None),
                ("Discharged", str(stats["discharged"]), MUTED, "🏠", None),
                ("Appointments today", str(stats["today_appointments"]), ACCENT, "📅", None),
            ]

        for i, (title, value, color, icon, on_click) in enumerate(card_data):
            card_outer, card = surface(cards_frame, bg=WHITE, pad=18)
            card_outer.grid(row=0, column=i, padx=(0, 12) if i < 3 else 0, sticky="ew")
            cards_frame.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=("Segoe UI", 20), bg=WHITE).pack(anchor="w")
            tk.Label(card, text=value, font=("Segoe UI", 26, "bold"), fg=color, bg=WHITE).pack(anchor="w")
            tk.Label(card, text=title, font=FONT_SMALL, fg=MUTED, bg=WHITE).pack(anchor="w")

            if on_click:
                card_outer.configure(cursor="hand2")
                card.configure(cursor="hand2")
                bind_click_recursive(card_outer, on_click)
            else:
                card_outer.configure(cursor="arrow")
                card.configure(cursor="arrow")

        if role == "Doctor":
            # Recent patients table (doctor only)
            tk.Label(self.content, text="Recent Patients", font=FONT_HEAD,
                     fg=PRIMARY, bg=BG).pack(anchor="w", pady=(8, 10))
            self._render_patient_table(self.content, db.get_all_patients()[:8])
        elif role == "Admin":
            kpi = db.get_admin_kpis()
            outer, panel = surface(self.content, bg=WHITE, pad=18)
            outer.pack(fill="x", pady=(10, 0))
            tk.Label(panel, text="Operations overview", font=("Segoe UI", 13, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
            tk.Label(
                panel,
                text=(
                    f"Outstanding balance across unpaid invoices: {kpi['outstanding_total']:.2f}  •  "
                    f"Lab orders pending (Ordered / In progress): {kpi['lab_orders_pending']}"
                ),
                font=("Segoe UI", 10),
                fg=MUTED,
                bg=WHITE,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", pady=(8, 4))
            tk.Label(
                panel,
                text="Clinical patient records are only available to Doctors. Use Billing, Pharmacy, Lab, and Audit Log from the sidebar.",
                font=("Segoe UI", 10),
                fg=PRIMARY,
                bg=WHITE,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", pady=(4, 0))

            snap_outer, snap = surface(self.content, bg=WHITE, pad=14)
            snap_outer.pack(fill="both", expand=True, pady=(14, 0))
            tk.Label(snap, text="Recent audit activity", font=("Segoe UI", 11, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w", pady=(0, 8))
            cols = ("Time", "User", "Action", "Details")
            tree = ttk.Treeview(snap, columns=cols, show="headings", height=8)
            for c, w in zip(cols, [160, 120, 160, 420]):
                tree.heading(c, text=c)
                tree.column(c, width=w, anchor="w")
            sb = ttk.Scrollbar(snap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            for row in db.get_audit_logs(40):
                ts, uname, action, etype, eid, details = row
                detail_short = (details or "")[:180]
                tree.insert("", "end", values=(ts, uname, action, detail_short))
            foot = tk.Frame(snap, bg=WHITE)
            foot.pack(fill="x", pady=(10, 0))
            more = tk.Button(foot, text="Open full Audit Log →", command=self.show_audit_log)
            style_button(more, SECONDARY)
            more.pack(side="left")
        else:
            outer, panel = surface(self.content, bg=WHITE, pad=18)
            outer.pack(fill="x", pady=(10, 0))
            tk.Label(panel, text="Welcome", font=("Segoe UI", 13, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
            tk.Label(
                panel,
                text="Use the left menu to access your assigned workflow.",
                font=("Segoe UI", 10),
                fg=MUTED,
                bg=WHITE,
            ).pack(anchor="w", pady=(6, 0))

        # Quick action buttons
        btn_frame = tk.Frame(self.content, bg=BG)
        btn_frame.pack(fill="x", pady=(16, 0))
        if role == "Doctor":
            add_btn = tk.Button(btn_frame, text="+ Register New Patient",
                                command=self.open_add_patient, **{})
            style_button(add_btn, PRIMARY)
            add_btn.pack(side="left", padx=(0, 10))

            appt_btn = tk.Button(btn_frame, text="📅 Book Appointment",
                                 command=self.open_add_appointment)
            style_button(appt_btn, SECONDARY)
            appt_btn.pack(side="left")

        if role == "Admin":
            backup_btn = tk.Button(btn_frame, text="💾 Backup Database", command=self.backup_database)
            style_button(backup_btn, ACCENT, fg=PRIMARY)
            backup_btn.pack(side="right")

            export_btn = tk.Button(btn_frame, text="⬇ Export CSV", command=self.open_export_menu)
            style_button(export_btn, WHITE, fg=PRIMARY)
            export_btn.configure(activebackground="#eef4fb", activeforeground=PRIMARY)
            export_btn.pack(side="right", padx=(0, 10))

            hub_btn = tk.Button(btn_frame, text="💾 Backups / Exports hub", command=self.show_backups_exports)
            style_button(hub_btn, SECONDARY)
            hub_btn.pack(side="right", padx=(0, 10))

    # ══════════════════════════
    #  PATIENTS PAGE
    # ══════════════════════════
    def show_patients(self, initial_filter: str = "All"):
        role = (self.current_user or {}).get("role", "")
        if role != "Doctor":
            messagebox.showwarning("Access Denied", "Only Doctors can access the Patients list.")
            self.show_dashboard()
            return
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
        # Persist filter var across navigations so Dashboard shortcuts work.
        self.filter_var = tk.StringVar(value=initial_filter if initial_filter in ("All", "Active", "Discharged") else "All")
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
        tree.tag_configure("hover",      background="#e8f1fb", foreground=PRIMARY)

        # Force readable hover styling (Treeview doesn't reliably support a theme hover state).
        tree._hover_iid = None
        tree._hover_prev_tags = {}

        def clear_hover():
            iid = getattr(tree, "_hover_iid", None)
            if not iid:
                return
            prev = tree._hover_prev_tags.get(iid)
            if prev is not None:
                tree.item(iid, tags=prev)
            tree._hover_iid = None

        def on_motion(e):
            iid = tree.identify_row(e.y)
            if iid == getattr(tree, "_hover_iid", None):
                return
            # Restore previous hover row
            clear_hover()
            if not iid:
                return
            # Don't override selected row styling
            if iid in tree.selection():
                return
            prev_tags = tree.item(iid, "tags")
            tree._hover_prev_tags[iid] = prev_tags
            tree.item(iid, tags=tuple(prev_tags) + ("hover",))
            tree._hover_iid = iid

        tree.bind("<Motion>", on_motion)
        tree.bind("<Leave>", lambda e: clear_hover())

        def open_profile(_=None):
            sel = tree.selection()
            if not sel:
                return
            pid = int(tree.item(sel[0])["values"][0])
            self.open_patient_profile(pid)

        tree.bind("<Double-1>", open_profile)

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

    def open_patient_profile(self, patient_id: int):
        p = db.get_patient(patient_id)
        if not p:
            messagebox.showerror("Not found", f"Patient ID {patient_id} not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Patient Profile — {p[1]} (ID {p[0]})")
        win.geometry("980x650")
        win.configure(bg=BG)
        win.grab_set()

        role = (self.current_user or {}).get("role", "")

        # Header card
        outer, header = surface(win, bg=WHITE, pad=16)
        outer.pack(fill="x", padx=18, pady=(18, 12))

        left = tk.Frame(header, bg=WHITE)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=p[1], font=("Segoe UI", 18, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
        subtitle = f"ID {p[0]}  •  {p[3]}  •  Age {p[2]}  •  Status: {p[6]}"
        tk.Label(left, text=subtitle, font=("Segoe UI", 10), fg=MUTED, bg=WHITE).pack(anchor="w", pady=(2, 0))
        tk.Label(left, text=f"Contact: {p[4]}    Condition: {p[5]}", font=("Segoe UI", 10), fg=PRIMARY, bg=WHITE).pack(anchor="w", pady=(6, 0))

        quick = tk.Frame(header, bg=WHITE)
        quick.pack(side="right", anchor="e")
        if role in ("Admin", "Reception", "Doctor"):
            appt_btn = tk.Button(quick, text="📅 Book Appointment", command=lambda: self.open_add_appointment(p[0], p[1]))
            style_button(appt_btn, SECONDARY)
            appt_btn.pack(side="right", padx=(10, 0))
        if role in ("Admin", "Doctor"):
            enc_btn = tk.Button(quick, text="+ New Encounter", command=lambda: self.open_add_encounter(p[0], refresh_callback=lambda: self._refresh_profile_tabs(win, p[0])))
            style_button(enc_btn, PRIMARY)
            enc_btn.pack(side="right")

        # Tabs
        body_outer, body = surface(win, bg=WHITE, pad=10)
        body_outer.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True)

        # Role-based profile tabs
        if role == "Nurse":
            tab_keys = ["Vitals"]
        elif role == "Doctor":
            tab_keys = ["Encounters", "Lab", "Prescriptions", "Vitals", "Appointments"]
        else:
            tab_keys = ["Encounters", "Appointments", "Billing", "Lab", "Prescriptions", "Vitals"]

        tabs = {}
        for key in tab_keys:
            frame = tk.Frame(nb, bg=WHITE)
            nb.add(frame, text=key)
            tabs[key] = frame

        # Store refs for refresh
        win._profile_patient_id = p[0]
        win._profile_tabs = tabs

        self._refresh_profile_tabs(win, p[0])

    def _refresh_profile_tabs(self, win: tk.Toplevel, patient_id: int):
        tabs = getattr(win, "_profile_tabs", {})
        if not tabs:
            return

        encs = db.get_patient_encounters(patient_id)

        # Encounters
        if "Encounters" in tabs:
            f = tabs["Encounters"]
            for w in f.winfo_children():
                w.destroy()
            cols = ("ID", "Type", "Doctor", "Reason", "Status", "Started", "Closed")
            tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("ID", width=60, anchor="center")
            tree.column("Type", width=110, anchor="center")
            tree.column("Doctor", width=180, anchor="w")
            tree.column("Reason", width=240, anchor="w")
            tree.column("Status", width=90, anchor="center")
            tree.column("Started", width=140, anchor="center")
            tree.column("Closed", width=140, anchor="center")
            tree.pack(fill="both", expand=True, padx=10, pady=10)
            for e in encs:
                tree.insert("", "end", values=e)

            # Only Doctor/Admin can close encounters
            role = (self.current_user or {}).get("role", "")
            if role in ("Admin", "Doctor"):
                btn_row = tk.Frame(f, bg=WHITE)
                btn_row.pack(fill="x", padx=10, pady=(0, 10))

                def close_selected():
                    sel = tree.selection()
                    if not sel:
                        messagebox.showwarning("Select", "Select an encounter first.", parent=win)
                        return
                    enc_id = int(tree.item(sel[0])["values"][0])
                    if messagebox.askyesno("Close", "Close this encounter?", parent=win):
                        db.close_encounter(enc_id)
                        if self.current_user:
                            db.log_audit(self.current_user["id"], self.current_user["username"], "CLOSE_ENCOUNTER", "encounters", enc_id, "Closed encounter")
                        self._refresh_profile_tabs(win, patient_id)

                close_btn = tk.Button(btn_row, text="Close Encounter", command=close_selected)
                style_button(close_btn, ACCENT, fg=PRIMARY)
                close_btn.pack(side="left")

        # Appointments
        if "Appointments" in tabs:
            f = tabs["Appointments"]
            for w in f.winfo_children():
                w.destroy()
            appts = db.get_patient_appointments(patient_id)
            cols = ("ID", "Doctor", "Date", "Time", "Notes", "Status")
            tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
            for c in cols:
                tree.heading(c, text=c)
            tree.column("ID", width=60, anchor="center")
            tree.column("Doctor", width=180, anchor="w")
            tree.column("Date", width=120, anchor="center")
            tree.column("Time", width=80, anchor="center")
            tree.column("Notes", width=360, anchor="w")
            tree.column("Status", width=100, anchor="center")
            tree.pack(fill="both", expand=True, padx=10, pady=10)
            for a in appts:
                tree.insert("", "end", values=(a[0], a[3], a[4], a[5], a[6] or "", a[7]))

        # Billing
        if "Billing" in tabs:
            f = tabs["Billing"]
            for w in f.winfo_children():
                w.destroy()
            invoices = db.get_patient_invoices(patient_id)
            cols = ("Invoice ID", "Status", "Created", "Total", "Paid", "Balance")
            tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
            for c in cols:
                tree.heading(c, text=c)
            for c, w in zip(cols, [90, 120, 160, 90, 90, 90]):
                tree.column(c, width=w, anchor="center" if c != "Status" else "w")
            tree.pack(fill="both", expand=True, padx=10, pady=10)
            for inv in invoices:
                inv_id, status, created, total, paid = inv
                bal = float(total) - float(paid)
                tree.insert("", "end", values=(inv_id, status, created, f"{total:.2f}", f"{paid:.2f}", f"{bal:.2f}"))

            btn_row = tk.Frame(f, bg=WHITE)
            btn_row.pack(fill="x", padx=10, pady=(0, 10))

            def new_invoice():
                self.open_create_invoice(patient_id, refresh_callback=lambda: self._refresh_profile_tabs(win, patient_id))

            ni = tk.Button(btn_row, text="+ New Invoice", command=new_invoice)
            style_button(ni, SECONDARY)
            ni.pack(side="left")

        # Lab & Prescriptions & Vitals show via selected encounter (if any)
        # To keep v1 simple: show most recent encounter's items
        latest_enc_id = encs[0][0] if encs else None

        # Lab
        if "Lab" in tabs:
            f = tabs["Lab"]
            for w in f.winfo_children():
                w.destroy()
            if not latest_enc_id:
                tk.Label(f, text="No encounters yet. Create an encounter to add lab orders.", bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(pady=18)
            else:
                orders = db.get_encounter_lab_orders(latest_enc_id)
                cols = ("Order ID", "Test", "Priority", "Status", "Ordered At", "Result")
                tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
                for c in cols:
                    tree.heading(c, text=c)
                tree.column("Order ID", width=80, anchor="center")
                tree.column("Test", width=220, anchor="w")
                tree.column("Priority", width=90, anchor="center")
                tree.column("Status", width=110, anchor="center")
                tree.column("Ordered At", width=160, anchor="center")
                tree.column("Result", width=280, anchor="w")
                tree.pack(fill="both", expand=True, padx=10, pady=10)
                for o in orders:
                    tree.insert("", "end", values=o)

                btn_row = tk.Frame(f, bg=WHITE)
                btn_row.pack(fill="x", padx=10, pady=(0, 10))
                role = (self.current_user or {}).get("role", "")
                if role in ("Admin", "Doctor"):
                    add_o = tk.Button(btn_row, text="+ Lab Order", command=lambda: self.open_add_lab_order(latest_enc_id, refresh_callback=lambda: self._refresh_profile_tabs(win, patient_id)))
                    style_button(add_o, PRIMARY)
                    add_o.pack(side="left", padx=(0, 10))
                add_r = tk.Button(btn_row, text="Add/Update Result", command=lambda: self.open_set_lab_result(tree, refresh_callback=lambda: self._refresh_profile_tabs(win, patient_id)))
                style_button(add_r, ACCENT, fg=PRIMARY)
                add_r.pack(side="left")

        # Prescriptions
        if "Prescriptions" in tabs:
            f = tabs["Prescriptions"]
            for w in f.winfo_children():
                w.destroy()
            if not latest_enc_id:
                tk.Label(f, text="No encounters yet. Create an encounter to add prescriptions.", bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(pady=18)
            else:
                rx = db.get_encounter_prescriptions(latest_enc_id)
                cols = ("ID", "Drug", "Dosage", "Frequency", "Duration", "Status", "Created")
                tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
                for c in cols:
                    tree.heading(c, text=c)
                tree.column("ID", width=60, anchor="center")
                tree.column("Drug", width=200, anchor="w")
                tree.column("Dosage", width=130, anchor="w")
                tree.column("Frequency", width=130, anchor="w")
                tree.column("Duration", width=110, anchor="w")
                tree.column("Status", width=90, anchor="center")
                tree.column("Created", width=140, anchor="center")
                tree.pack(fill="both", expand=True, padx=10, pady=10)
                for r in rx:
                    tree.insert("", "end", values=r)
                role = (self.current_user or {}).get("role", "")
                if role in ("Admin", "Doctor"):
                    btn_row = tk.Frame(f, bg=WHITE)
                    btn_row.pack(fill="x", padx=10, pady=(0, 10))
                    add_rx = tk.Button(btn_row, text="+ Add Prescription", command=lambda: self.open_add_prescription(latest_enc_id, refresh_callback=lambda: self._refresh_profile_tabs(win, patient_id)))
                    style_button(add_rx, PRIMARY)
                    add_rx.pack(side="left")

        # Vitals
        if "Vitals" in tabs:
            f = tabs["Vitals"]
            for w in f.winfo_children():
                w.destroy()
            if not latest_enc_id:
                tk.Label(f, text="No encounters yet. Create an encounter to record vitals.", bg=WHITE, fg=MUTED, font=("Segoe UI", 10)).pack(pady=18)
            else:
                vitals = db.get_encounter_vitals(latest_enc_id)
                cols = ("Time", "Temp", "Pulse", "BP", "Resp", "SpO2", "Weight", "Height")
                tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
                for c in cols:
                    tree.heading(c, text=c)
                tree.column("Time", width=160, anchor="center")
                tree.column("Temp", width=80, anchor="center")
                tree.column("Pulse", width=80, anchor="center")
                tree.column("BP", width=90, anchor="center")
                tree.column("Resp", width=80, anchor="center")
                tree.column("SpO2", width=80, anchor="center")
                tree.column("Weight", width=90, anchor="center")
                tree.column("Height", width=90, anchor="center")
                tree.pack(fill="both", expand=True, padx=10, pady=10)
                for v in vitals:
                    ts, temp, pulse, sys, dia, resp, spo2, wkg, hcm = v
                    bp = f"{sys}/{dia}" if sys is not None and dia is not None else ""
                    tree.insert("", "end", values=(ts, temp or "", pulse or "", bp, resp or "", spo2 or "", wkg or "", hcm or ""))
                btn_row = tk.Frame(f, bg=WHITE)
                btn_row.pack(fill="x", padx=10, pady=(0, 10))
                add_v = tk.Button(btn_row, text="+ Record Vitals", command=lambda: self.open_add_vitals(latest_enc_id, refresh_callback=lambda: self._refresh_profile_tabs(win, patient_id)))
                style_button(add_v, PRIMARY)
                add_v.pack(side="left")

    # ── Profile helpers (modals) ──
    def open_add_encounter(self, patient_id: int, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("New Encounter")
        # Make sure the create button is visible on all screens
        win.geometry("520x640")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Create Encounter", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        form_outer, form = surface(win, bg=WHITE, pad=18)
        form_outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Type", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        enc_type = tk.StringVar(value="Outpatient")
        type_combo = ttk.Combobox(form, textvariable=enc_type, values=["Outpatient", "Inpatient", "ER"], state="readonly")
        type_combo.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Doctor (optional)", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        docs = db.get_doctors(active_only=True)
        doc_map = {"": None}
        doc_values = [""]
        for d in docs:
            doc_values.append(f"{d[0]} — {d[1]}")
            doc_map[f"{d[0]} — {d[1]}"] = int(d[0])
        doc_var = tk.StringVar(value="")
        doc_combo = ttk.Combobox(form, textvariable=doc_var, values=doc_values, state="readonly")
        doc_combo.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Reason", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        reason_e = tk.Entry(form)
        style_entry(reason_e)
        reason_e.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Notes", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        notes = tk.Text(form, height=8, font=("Segoe UI", 10), bg=WHITE, fg=PRIMARY, relief="flat", highlightbackground=PANEL_BORDER, highlightthickness=1)
        notes.pack(fill="both", expand=True, pady=(4, 10))

        def submit():
            did = doc_map.get(doc_var.get(), None)
            eid = db.add_encounter(patient_id, did, enc_type.get(), reason_e.get().strip(), notes.get("1.0", "end").strip())
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_ENCOUNTER", "encounters", eid, f"Created encounter for patient_id={patient_id}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", pady=(0, 16))
        btn = tk.Button(btn_row, text="Create Encounter", command=submit)
        style_button(btn, PRIMARY)
        btn.pack()

    def open_add_vitals(self, encounter_id: int, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("Record Vitals")
        win.geometry("520x520")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Record Vitals", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        form_outer, form = surface(win, bg=WHITE, pad=18)
        form_outer.pack(fill="both", expand=True, padx=18, pady=12)

        def field_row(label_txt):
            tk.Label(form, text=label_txt, bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            e = tk.Entry(form)
            style_entry(e)
            e.pack(fill="x", pady=(4, 10))
            return e

        temp = field_row("Temperature (°C)")
        pulse = field_row("Pulse (bpm)")
        sys = field_row("Systolic (mmHg)")
        dia = field_row("Diastolic (mmHg)")
        resp = field_row("Respiration (rpm)")
        spo2 = field_row("SpO2 (%)")
        wkg = field_row("Weight (kg)")
        hcm = field_row("Height (cm)")

        def num_or_none(s, t=float):
            s = s.strip()
            if not s:
                return None
            return t(s)

        def submit():
            try:
                db.add_vitals(
                    encounter_id,
                    temperature=num_or_none(temp.get(), float),
                    pulse=num_or_none(pulse.get(), int),
                    systolic=num_or_none(sys.get(), int),
                    diastolic=num_or_none(dia.get(), int),
                    respiration=num_or_none(resp.get(), int),
                    spo2=num_or_none(spo2.get(), int),
                    weight_kg=num_or_none(wkg.get(), float),
                    height_cm=num_or_none(hcm.get(), float),
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not save vitals.\n\n{e}", parent=win)
                return
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_VITALS", "vitals", None, f"Recorded vitals for encounter_id={encounter_id}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Save Vitals", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_add_prescription(self, encounter_id: int, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("Add Prescription")
        win.geometry("520x520")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Add Prescription", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        form_outer, form = surface(win, bg=WHITE, pad=18)
        form_outer.pack(fill="both", expand=True, padx=18, pady=12)

        def field(label_txt):
            tk.Label(form, text=label_txt, bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            e = tk.Entry(form)
            style_entry(e)
            e.pack(fill="x", pady=(4, 10))
            return e

        drug = field("Drug name")
        dosage = field("Dosage")
        freq = field("Frequency")
        dur = field("Duration")
        tk.Label(form, text="Notes", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        notes = tk.Text(form, height=6, font=("Segoe UI", 10), bg=WHITE, fg=PRIMARY, relief="flat", highlightbackground=PANEL_BORDER, highlightthickness=1)
        notes.pack(fill="both", expand=True, pady=(4, 10))

        def submit():
            if not drug.get().strip():
                messagebox.showwarning("Missing", "Drug name is required.", parent=win)
                return
            rid = db.add_prescription(encounter_id, drug.get(), dosage.get(), freq.get(), dur.get(), notes.get("1.0", "end").strip())
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_PRESCRIPTION", "prescriptions", rid, f"Added prescription for encounter_id={encounter_id}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Add Prescription", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_add_lab_order(self, encounter_id: int, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("Lab Order")
        win.geometry("520x360")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Create Lab Order", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        form_outer, form = surface(win, bg=WHITE, pad=18)
        form_outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Test name", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        test = tk.Entry(form)
        style_entry(test)
        test.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Priority", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        pr = tk.StringVar(value="Routine")
        combo = ttk.Combobox(form, textvariable=pr, values=["Routine", "Urgent"], state="readonly")
        combo.pack(fill="x", pady=(4, 10))

        def submit():
            if not test.get().strip():
                messagebox.showwarning("Missing", "Test name is required.", parent=win)
                return
            oid = db.add_lab_order(encounter_id, test.get(), pr.get())
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_LAB_ORDER", "lab_orders", oid, f"Added lab order for encounter_id={encounter_id}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Create Order", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_set_lab_result(self, orders_tree: ttk.Treeview, refresh_callback=None):
        sel = orders_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a lab order first.")
            return
        order_id = int(orders_tree.item(sel[0])["values"][0])

        win = tk.Toplevel(self)
        win.title("Lab Result")
        win.geometry("620x420")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text=f"Lab Result (Order {order_id})", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        form_outer, form = surface(win, bg=WHITE, pad=18)
        form_outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Result text", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        txt = tk.Text(form, height=10, font=("Segoe UI", 10), bg=WHITE, fg=PRIMARY, relief="flat", highlightbackground=PANEL_BORDER, highlightthickness=1)
        txt.pack(fill="both", expand=True, pady=(4, 10))

        def submit():
            db.set_lab_result(order_id, txt.get("1.0", "end").strip())
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "SET_LAB_RESULT", "lab_results", order_id, "Updated lab result")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Save Result", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_create_invoice(self, patient_id: int, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("Create Invoice")
        win.geometry("720x560")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Create Invoice", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        outer, form = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        invoice_id = db.create_invoice(patient_id)

        tk.Label(form, text=f"Invoice #{invoice_id}", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(form, text="Add items below", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        cols = ("Description", "Qty", "Unit price")
        items_tree = ttk.Treeview(form, columns=cols, show="headings", height=8)
        for c in cols:
            items_tree.heading(c, text=c)
        items_tree.column("Description", width=360, anchor="w")
        items_tree.column("Qty", width=80, anchor="center")
        items_tree.column("Unit price", width=120, anchor="center")
        items_tree.pack(fill="x", pady=(0, 10))

        row = tk.Frame(form, bg=WHITE)
        row.pack(fill="x")
        desc = tk.Entry(row)
        style_entry(desc)
        desc.pack(side="left", fill="x", expand=True, padx=(0, 10))
        qty = tk.Entry(row, width=8)
        style_entry(qty)
        qty.insert(0, "1")
        qty.pack(side="left", padx=(0, 10))
        price = tk.Entry(row, width=10)
        style_entry(price)
        price.insert(0, "0")
        price.pack(side="left")

        def add_item():
            d = desc.get().strip()
            if not d:
                return
            try:
                q = float(qty.get().strip() or "1")
                pr = float(price.get().strip() or "0")
            except ValueError:
                messagebox.showwarning("Invalid", "Qty and Unit price must be numbers.", parent=win)
                return
            db.add_invoice_item(invoice_id, d, q, pr)
            items_tree.insert("", "end", values=(d, q, pr))
            desc.delete(0, "end")
            qty.delete(0, "end")
            qty.insert(0, "1")
            price.delete(0, "end")
            price.insert(0, "0")

        add_btn = tk.Button(form, text="+ Add Item", command=add_item)
        style_button(add_btn, SECONDARY)
        add_btn.pack(anchor="w", pady=(10, 10))

        pay_row = tk.Frame(form, bg=WHITE)
        pay_row.pack(fill="x", pady=(6, 0))
        tk.Label(pay_row, text="Payment (optional)", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(side="left")
        pay_amt = tk.Entry(pay_row, width=12)
        style_entry(pay_amt)
        pay_amt.insert(0, "")
        pay_amt.pack(side="right")

        def finish():
            amt = pay_amt.get().strip()
            if amt:
                try:
                    db.add_payment(invoice_id, float(amt), method="Cash")
                except ValueError:
                    messagebox.showwarning("Invalid", "Payment must be a number.", parent=win)
                    return
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "CREATE_INVOICE", "invoices", invoice_id, f"Created invoice for patient_id={patient_id}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Finish Invoice", command=finish)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

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
    #  STAFF REGISTRY (ADMIN)
    # ══════════════════════════
    def show_staff_registry(self):
        self.clear_content()
        self.set_title("Staff registry")
        self._set_active_nav("📇  Staff registry")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        if not self.current_user or self.current_user.get("role") != "Admin":
            messagebox.showwarning("Access Denied", "Only Admin can manage staff accounts.")
            self.show_dashboard()
            return

        intro_outer, intro = surface(self.content, bg=WHITE, pad=16)
        intro_outer.pack(fill="x", pady=(0, 14))
        tk.Label(intro, text="Staff accounts", font=("Segoe UI", 13, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
        tk.Label(
            intro,
            text=(
                "Register accounts for StanCare: doctors, nurses, lab techs (numeric Login ID), pharmacists and reception "
                "(username), plus billing and other roles as needed. Match each account type to the welcome-screen tile "
                "that person uses to sign in."
            ),
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=WHITE,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Register staff member", command=self.open_add_user)
        style_button(add_btn, SECONDARY)
        add_btn.pack(side="left")

        tk.Label(bar, text="Filter:", font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="left", padx=(22, 8))
        role_filter_var = tk.StringVar(value="All roles")
        filter_combo = ttk.Combobox(
            bar,
            textvariable=role_filter_var,
            values=[
                "All roles",
                "Doctor",
                "Nurse",
                "Lab",
                "Pharmacist",
                "Billing",
                "Reception",
                "Admin",
            ],
            state="readonly",
            width=16,
        )
        filter_combo.pack(side="left")

        cols = ("ID", "Username", "Full Name", "Role", "Login ID", "Active", "Created")
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = [44, 120, 170, 88, 72, 56, 150]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            anchor = "w" if col in ("Username", "Full Name") else "center"
            tree.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def refresh_rows():
            for iid in tree.get_children():
                tree.delete(iid)
            filt = role_filter_var.get()
            for u in db.get_users():
                uid, username, full_name, role, login_id, active, created_at = u
                if filt != "All roles" and role != filt:
                    continue
                lid_disp = str(login_id) if login_id is not None else "—"
                tree.insert(
                    "",
                    "end",
                    values=(uid, username, full_name or "", role, lid_disp, "Yes" if active else "No", created_at),
                )

        refresh_rows()
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: refresh_rows())

        def toggle_active():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select a staff member.")
                return
            vals = tree.item(sel[0])["values"]
            uid = int(vals[0])
            username = vals[1]
            active_now = vals[5] == "Yes"
            if uid == self.current_user["id"]:
                messagebox.showwarning("Not allowed", "You cannot disable your own account.")
                return
            if messagebox.askyesno("Confirm", f"{'Disable' if active_now else 'Enable'} account '{username}'?"):
                db.set_user_active(uid, not active_now, changed_by_user=self.current_user)
                self.show_staff_registry()

        def reset_password():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select a staff member.")
                return
            vals = tree.item(sel[0])["values"]
            uid = int(vals[0])
            username = vals[1]
            self.open_reset_password(uid, username)

        btn_frame = tk.Frame(self.content, bg=BG)
        btn_frame.pack(fill="x", pady=(10, 0))
        t_btn = tk.Button(btn_frame, text="Enable / Disable", command=toggle_active)
        style_button(t_btn, ACCENT, fg=PRIMARY)
        t_btn.pack(side="left", padx=(0, 10))
        r_btn = tk.Button(btn_frame, text="Reset password", command=reset_password)
        style_button(r_btn, PRIMARY)
        r_btn.pack(side="left")

    def show_audit_log(self):
        self.clear_content()
        self.set_title("Audit Log")
        self._set_active_nav("📜  Audit Log")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        if not self.current_user or self.current_user.get("role") != "Admin":
            messagebox.showwarning("Access Denied", "Only Admin can view the audit log.")
            self.show_dashboard()
            return

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        tk.Label(bar, text="Search:", font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="left", padx=(0, 8))
        search_var = tk.StringVar()

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("Time", "User", "Action", "Entity", "ID", "Details")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = [150, 110, 140, 90, 60, 380]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            anchor = "w" if col in ("User", "Details", "Action") else "center"
            tree.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def refresh():
            for i in tree.get_children():
                tree.delete(i)
            q = search_var.get().strip()
            for row in db.get_audit_logs_filtered(q, limit=600):
                ts, uname, action, etype, eid, details = row
                eid_disp = "" if eid is None or eid == "" else str(eid)
                tree.insert("", "end", values=(ts, uname, action, etype or "", eid_disp, details or ""))

        search_entry = tk.Entry(bar, textvariable=search_var, width=36)
        style_entry(search_entry)
        search_entry.pack(side="left")
        search_btn = tk.Button(bar, text="Apply", command=refresh)
        style_button(search_btn, SECONDARY)
        search_btn.pack(side="left", padx=(10, 0))
        search_var.trace_add("write", lambda *_: refresh())
        refresh()

    def show_backups_exports(self):
        self.clear_content()
        self.set_title("Backups / Exports")
        self._set_active_nav("💾  Backups/Exports")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        if not self.current_user or self.current_user.get("role") != "Admin":
            messagebox.showwarning("Access Denied", "Only Admin can access backups and exports.")
            self.show_dashboard()
            return

        outer, panel = surface(self.content, bg=WHITE, pad=22)
        outer.pack(fill="both", expand=True)

        tk.Label(panel, text="Data protection", font=("Segoe UI", 14, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
        tk.Label(
            panel,
            text="Backups are stored under the project folder in backups/. CSV exports go to exports/.",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=WHITE,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(8, 20))

        row = tk.Frame(panel, bg=WHITE)
        row.pack(fill="x", pady=(0, 12))

        b1 = tk.Button(row, text="💾 Backup database now", command=self.backup_database)
        style_button(b1, ACCENT, fg=PRIMARY)
        b1.pack(side="left", padx=(0, 12))

        b2 = tk.Button(row, text="⬇ Export CSV…", command=self.open_export_menu)
        style_button(b2, SECONDARY)
        b2.pack(side="left")

    def open_add_user(self):
        win = tk.Toplevel(self)
        win.title("Register staff member")
        # Window got taller after adding Login ID; increase height so the button stays visible.
        win.geometry("480x660")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Register staff member", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(20, 4))
        tk.Label(win, text="Account type, credentials, and Login ID where required", font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(0, 16))

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

        tk.Label(
            form,
            text="Login ID (required for Doctor, Nurse, Lab · numeric, unique)",
            font=FONT_SMALL,
            fg=PRIMARY,
            bg=BG,
            anchor="w",
        ).pack(fill="x")
        login_id_e = tk.Entry(form)
        style_entry(login_id_e)
        login_id_e.pack(fill="x", pady=(2, 10))

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
            lid = login_id_e.get().strip()
            if role in ("Doctor", "Nurse", "Lab"):
                if not lid.isdigit():
                    messagebox.showwarning(
                        "Login ID",
                        "Doctor, Nurse, and Lab roles must have a numeric Login ID.",
                        parent=win,
                    )
                    return
            elif lid and not lid.isdigit():
                messagebox.showwarning("Login ID", "Login ID must be numeric.", parent=win)
                return
            try:
                uid = db.create_user(username=username, password=pw, role=role, full_name=full_name, created_by_user=self.current_user)
                if role in ("Doctor", "Nurse", "Lab"):
                    db.set_user_login_id(uid, int(lid), doctor_id=None)
                elif lid:
                    db.set_user_login_id(uid, int(lid), doctor_id=None)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create user.\n\n{e}", parent=win)
                return
            messagebox.showinfo("Success", f"Staff account '{username}' created.", parent=win)
            win.destroy()
            self.show_staff_registry()

        btn = tk.Button(win, text="Create account", command=submit)
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
    #  ENCOUNTERS
    # ══════════════════════════
    def show_encounters(self):
        self.clear_content()
        self.set_title("Encounters")
        self._set_active_nav("🩺  Encounters")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        tk.Label(bar, text="Status:", font=FONT_SMALL, bg=BG, fg=MUTED).pack(side="right", padx=(0, 6))
        status_var = tk.StringVar(value="All")
        combo = ttk.Combobox(bar, textvariable=status_var, values=["All", "Open", "Closed"], state="readonly", width=10)
        combo.pack(side="right")

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("ID", "Patient", "Doctor", "Type", "Reason", "Status", "Started")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=70, anchor="center")
        tree.column("Patient", width=200, anchor="w")
        tree.column("Doctor", width=180, anchor="w")
        tree.column("Type", width=110, anchor="center")
        tree.column("Reason", width=220, anchor="w")
        tree.column("Status", width=90, anchor="center")
        tree.column("Started", width=160, anchor="center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def refresh():
            for i in tree.get_children():
                tree.delete(i)
            st = status_var.get()
            rows = db.get_all_encounters(None if st == "All" else st)
            for r in rows:
                tree.insert("", "end", values=r)

        combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        refresh()

        btn_row = tk.Frame(self.content, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))

        def open_patient():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select an encounter first.")
                return
            # We only have patient name in list; open patient search by name is ambiguous, so just show info.
            messagebox.showinfo("Tip", "Open a patient profile by double-clicking a patient in the Patients page.")

        b = tk.Button(btn_row, text="Open Patient Profile", command=open_patient)
        style_button(b, ACCENT, fg=PRIMARY)
        b.pack(side="left")

    # ══════════════════════════
    #  DOCTORS
    # ══════════════════════════
    def show_doctors(self):
        self.clear_content()
        self.set_title("Doctors")
        self._set_active_nav("👨‍⚕️  Doctors")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Add Doctor", command=self.open_add_doctor)
        style_button(add_btn, SECONDARY)
        add_btn.pack(side="left")
        dep_btn = tk.Button(bar, text="+ Add Department", command=self.open_add_department)
        style_button(dep_btn, PRIMARY)
        dep_btn.pack(side="left", padx=(10, 0))

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("ID", "Name", "Department", "Phone", "Email", "Active")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60, anchor="center")
        tree.column("Name", width=220, anchor="w")
        tree.column("Department", width=160, anchor="w")
        tree.column("Phone", width=140, anchor="w")
        tree.column("Email", width=220, anchor="w")
        tree.column("Active", width=80, anchor="center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def refresh():
            for i in tree.get_children():
                tree.delete(i)
            for d in db.get_doctors(active_only=False):
                tree.insert("", "end", values=(d[0], d[1], d[2], d[3] or "", d[4] or "", "Yes" if d[5] else "No"))

        refresh()

        btn_row = tk.Frame(self.content, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))

        def toggle():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a doctor.")
                return
            vals = tree.item(sel[0])["values"]
            did = int(vals[0])
            active_now = vals[5] == "Yes"
            if messagebox.askyesno("Confirm", f"{'Disable' if active_now else 'Enable'} this doctor?"):
                db.set_doctor_active(did, not active_now)
                if self.current_user:
                    db.log_audit(self.current_user["id"], self.current_user["username"], "SET_DOCTOR_ACTIVE", "doctors", did, f"Set active={not active_now}")
                refresh()

        t = tk.Button(btn_row, text="Enable/Disable", command=toggle)
        style_button(t, ACCENT, fg=PRIMARY)
        t.pack(side="left")

    def open_add_department(self):
        win = tk.Toplevel(self)
        win.title("Add Department")
        win.geometry("420x260")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Add Department", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        outer, form = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Department name", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        name = tk.Entry(form)
        style_entry(name)
        name.pack(fill="x", pady=(4, 10))

        def submit():
            if not name.get().strip():
                return
            try:
                did = db.add_department(name.get())
            except Exception as e:
                messagebox.showerror("Error", f"Could not add department.\n\n{e}", parent=win)
                return
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_DEPARTMENT", "departments", did, f"Added department '{name.get().strip()}'")
            win.destroy()
            self.show_doctors()

        btn = tk.Button(win, text="Add Department", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_add_doctor(self):
        win = tk.Toplevel(self)
        win.title("Add Doctor")
        win.geometry("520x460")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Add Doctor", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        outer, form = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Full name", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        full = tk.Entry(form)
        style_entry(full)
        full.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Department", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        deps = db.get_departments()
        dep_map = {"": None}
        dep_values = [""]
        for d in deps:
            dep_values.append(f"{d[0]} — {d[1]}")
            dep_map[f"{d[0]} — {d[1]}"] = int(d[0])
        dep_var = tk.StringVar(value="")
        dep_combo = ttk.Combobox(form, textvariable=dep_var, values=dep_values, state="readonly")
        dep_combo.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Phone", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        phone = tk.Entry(form)
        style_entry(phone)
        phone.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Email", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        email = tk.Entry(form)
        style_entry(email)
        email.pack(fill="x", pady=(4, 10))

        def submit():
            if not full.get().strip():
                messagebox.showwarning("Missing", "Full name is required.", parent=win)
                return
            did = dep_map.get(dep_var.get(), None)
            try:
                doc_id = db.add_doctor(full.get(), did, phone.get(), email.get())
            except Exception as e:
                messagebox.showerror("Error", f"Could not add doctor.\n\n{e}", parent=win)
                return
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_DOCTOR", "doctors", doc_id, f"Added doctor '{full.get().strip()}'")
            win.destroy()
            self.show_doctors()

        btn = tk.Button(win, text="Add Doctor", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    # ══════════════════════════
    #  PHARMACY / INVENTORY
    # ══════════════════════════
    def show_pharmacy(self):
        self.clear_content()
        self.set_title("Pharmacy / Inventory")
        self._set_active_nav("💊  Pharmacy")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        bar = tk.Frame(self.content, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        add_btn = tk.Button(bar, text="+ Add Item", command=self.open_add_inventory_item)
        style_button(add_btn, SECONDARY)
        add_btn.pack(side="left")
        low_btn = tk.Button(bar, text="View Low Stock", command=self.show_low_stock)
        style_button(low_btn, ACCENT, fg=PRIMARY)
        low_btn.pack(side="left", padx=(10, 0))

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("ID", "SKU", "Name", "Category", "Unit", "Qty", "Reorder", "Updated")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        for c, w in zip(cols, [60, 90, 220, 140, 80, 80, 90, 160]):
            tree.column(c, width=w, anchor="w" if c in ("Name", "Category") else "center")

        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def refresh():
            for i in tree.get_children():
                tree.delete(i)
            for it in db.get_inventory_items():
                tree.insert("", "end", values=it)

        refresh()

        btn_row = tk.Frame(self.content, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))

        def adjust():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select an item first.")
                return
            vals = tree.item(sel[0])["values"]
            self.open_adjust_inventory(int(vals[0]), vals[2], refresh_callback=refresh)

        adj = tk.Button(btn_row, text="Adjust Stock", command=adjust)
        style_button(adj, PRIMARY)
        adj.pack(side="left")

    def show_low_stock(self):
        win = tk.Toplevel(self)
        win.title("Low Stock Items")
        win.geometry("820x480")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text="Low Stock Items", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        outer, frame = surface(win, bg=WHITE, pad=10)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        cols = ("ID", "SKU", "Name", "Category", "Unit", "Qty", "Reorder")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        for c, w in zip(cols, [60, 90, 260, 160, 80, 80, 90]):
            tree.column(c, width=w, anchor="w" if c in ("Name", "Category") else "center")
        tree.pack(fill="both", expand=True)
        for r in db.get_low_stock_items():
            tree.insert("", "end", values=r)

    def open_add_inventory_item(self):
        win = tk.Toplevel(self)
        win.title("Add Inventory Item")
        win.geometry("560x560")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Add Inventory Item", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        outer, form = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        def field(lbl, default=""):
            tk.Label(form, text=lbl, bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            e = tk.Entry(form)
            style_entry(e)
            if default:
                e.insert(0, default)
            e.pack(fill="x", pady=(4, 10))
            return e

        name = field("Name")
        sku = field("SKU (optional)")
        cat = field("Category")
        unit = field("Unit", "unit")
        qty = field("Starting Quantity", "0")
        reorder = field("Reorder Level", "0")

        def submit():
            if not name.get().strip():
                messagebox.showwarning("Missing", "Name is required.", parent=win)
                return
            try:
                iid = db.add_inventory_item(
                    name=name.get(),
                    sku=sku.get(),
                    category=cat.get(),
                    unit=unit.get(),
                    quantity=float(qty.get().strip() or "0"),
                    reorder_level=float(reorder.get().strip() or "0"),
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not add item.\n\n{e}", parent=win)
                return
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADD_INVENTORY_ITEM", "inventory_items", iid, f"Added inventory item '{name.get().strip()}'")
            win.destroy()
            self.show_pharmacy()

        btn = tk.Button(win, text="Add Item", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    def open_adjust_inventory(self, item_id: int, item_name: str, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title("Adjust Inventory")
        win.geometry("520x360")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Adjust Stock", font=FONT_TITLE, fg=PRIMARY, bg=BG).pack(pady=(18, 4))
        tk.Label(win, text=item_name, font=("Segoe UI", 10), fg=MUTED, bg=BG).pack(pady=(0, 10))
        outer, form = surface(win, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        tk.Label(form, text="Quantity change (use negative for stock-out)", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        delta = tk.Entry(form)
        style_entry(delta)
        delta.pack(fill="x", pady=(4, 10))

        tk.Label(form, text="Reason", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        reason = tk.Entry(form)
        style_entry(reason)
        reason.pack(fill="x", pady=(4, 10))

        def submit():
            try:
                d = float(delta.get().strip())
            except ValueError:
                messagebox.showwarning("Invalid", "Quantity change must be a number.", parent=win)
                return
            db.adjust_inventory(item_id, d, reason.get(), user_id=self.current_user["id"] if self.current_user else None)
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "ADJUST_INVENTORY", "inventory_items", item_id, f"delta={d} reason={reason.get().strip()}")
            if refresh_callback:
                refresh_callback()
            win.destroy()

        btn = tk.Button(win, text="Apply", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(pady=(0, 16))

    # ══════════════════════════
    #  LAB
    # ══════════════════════════
    def show_lab(self):
        self.clear_content()
        self.set_title("Lab")
        self._set_active_nav("🧪  Lab")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("Order ID", "Patient", "Test", "Priority", "Status", "Ordered At")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        for c, w in zip(cols, [80, 200, 260, 90, 110, 160]):
            tree.column(c, width=w, anchor="w" if c in ("Patient", "Test") else "center")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for r in db.get_all_lab_orders():
            tree.insert("", "end", values=r)

        btn_row = tk.Frame(self.content, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))
        tip = tk.Label(btn_row, text="To add orders/results, open a Patient Profile → Lab tab.", bg=BG, fg=MUTED, font=FONT_SMALL)
        tip.pack(side="left")

    # ══════════════════════════
    #  BILLING
    # ══════════════════════════
    def show_billing(self):
        self.clear_content()
        self.set_title("Billing")
        self._set_active_nav("💳  Billing")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        frame_outer, frame = surface(self.content, bg=WHITE, pad=10)
        frame_outer.pack(fill="both", expand=True)

        cols = ("Invoice ID", "Patient", "Status", "Created", "Total", "Paid", "Balance")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        for c, w in zip(cols, [90, 220, 140, 170, 90, 90, 90]):
            tree.column(c, width=w, anchor="w" if c == "Patient" else "center")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for inv in db.get_all_invoices():
            inv_id, pname, status, created, total, paid = inv
            bal = float(total) - float(paid)
            tree.insert("", "end", values=(inv_id, pname, status, created, f"{total:.2f}", f"{paid:.2f}", f"{bal:.2f}"))

        btn_row = tk.Frame(self.content, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))
        tip = tk.Label(btn_row, text="Create invoices from a Patient Profile → Billing tab.", bg=BG, fg=MUTED, font=FONT_SMALL)
        tip.pack(side="left")

    # ══════════════════════════
    #  NURSE VITALS STATION
    # ══════════════════════════
    def show_vitals_station(self):
        self.clear_content()
        self.set_title("Vitals")
        self._set_active_nav("🩺  Vitals")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        outer, panel = surface(self.content, bg=WHITE, pad=18)
        outer.pack(fill="x")
        tk.Label(panel, text="Record Vitals", font=("Segoe UI", 14, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
        tk.Label(panel, text="Enter Patient ID to record vitals (Nurse).", font=("Segoe UI", 10), fg=MUTED, bg=WHITE).pack(anchor="w", pady=(4, 12))

        row = tk.Frame(panel, bg=WHITE)
        row.pack(fill="x")
        pid = tk.Entry(row, width=20)
        style_entry(pid)
        pid.pack(side="left")

        def go():
            v = pid.get().strip()
            if not v.isdigit():
                messagebox.showwarning("Invalid", "Enter a numeric patient ID.")
                return
            self.open_patient_profile(int(v))

        btn = tk.Button(row, text="Open", command=go)
        style_button(btn, PRIMARY)
        btn.pack(side="left", padx=(10, 0))

    # ══════════════════════════
    #  LAB UPLOAD (LAB ROLE)
    # ══════════════════════════
    def show_lab_upload(self):
        self.clear_content()
        self.set_title("Lab Upload")
        self._set_active_nav("🧪  Lab Upload")
        if hasattr(self, "user_badge") and self.current_user:
            self.user_badge.configure(text=f"{self.current_user['username']} • {self.current_user['role']}")

        outer, panel = surface(self.content, bg=WHITE, pad=18)
        outer.pack(fill="both", expand=True)
        tk.Label(panel, text="Upload Lab Result", font=("Segoe UI", 14, "bold"), fg=PRIMARY, bg=WHITE).pack(anchor="w")
        tk.Label(panel, text="Enter Patient ID, test name, and result. It will attach to the latest encounter.", font=("Segoe UI", 10), fg=MUTED, bg=WHITE).pack(anchor="w", pady=(4, 12))

        def field(lbl):
            tk.Label(panel, text=lbl, bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            e = tk.Entry(panel)
            style_entry(e)
            e.pack(fill="x", pady=(4, 10))
            return e

        patient_id_e = field("Patient ID")
        test_name_e = field("Test name")
        tk.Label(panel, text="Priority", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        pr = tk.StringVar(value="Routine")
        pr_combo = ttk.Combobox(panel, textvariable=pr, values=["Routine", "Urgent"], state="readonly")
        pr_combo.pack(fill="x", pady=(4, 10))

        tk.Label(panel, text="Result text", bg=WHITE, fg=PRIMARY, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        result = tk.Text(panel, height=10, font=("Segoe UI", 10), bg=WHITE, fg=PRIMARY, relief="flat", highlightbackground=PANEL_BORDER, highlightthickness=1)
        result.pack(fill="both", expand=True, pady=(4, 10))

        def submit():
            pid_txt = patient_id_e.get().strip()
            if not pid_txt.isdigit():
                messagebox.showwarning("Invalid", "Patient ID must be numeric.")
                return
            pid_i = int(pid_txt)
            if not db.patient_exists(pid_i):
                messagebox.showwarning("Not found", f"Patient ID {pid_i} does not exist.")
                return
            test = test_name_e.get().strip()
            if not test:
                messagebox.showwarning("Missing", "Test name is required.")
                return
            enc_id = db.get_latest_encounter_id_for_patient(pid_i)
            if not enc_id:
                messagebox.showwarning("No encounter", "This patient has no encounters yet. A doctor must create an encounter first.")
                return
            oid = db.add_lab_order(enc_id, test, pr.get())
            db.set_lab_result(oid, result.get("1.0", "end").strip())
            if self.current_user:
                db.log_audit(self.current_user["id"], self.current_user["username"], "LAB_UPLOAD", "lab_orders", oid, f"patient_id={pid_i} test={test}")
            messagebox.showinfo("Saved", f"Lab result uploaded (Order {oid}).")
            patient_id_e.delete(0, "end")
            test_name_e.delete(0, "end")
            result.delete("1.0", "end")

        btn = tk.Button(panel, text="Upload Result", command=submit)
        style_button(btn, PRIMARY)
        btn.pack(anchor="w", pady=(6, 0))

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
