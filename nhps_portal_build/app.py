from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import re, json, os, random, string, uuid
from functools import wraps
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-abc123")

USERS_FILE       = "users.json"
CLASSES_FILE     = "classes.json"
WRITEUPS_FILE    = "writeups.json"
PERMISSIONS_FILE = "permissions.json"

ALLOWED_DOMAIN  = "nhps.net"
STUDENT_PATTERN = re.compile(r"^\d{6}$")
STAFF_PATTERN   = re.compile(r"^[a-zA-Z]+\.[a-zA-Z]+$")

GRADE_CHOICES = ["7", "8"]

STAFF_TITLES = [
    "Teacher", "Counselor", "Administrator", "IT / Developer",
    "Paraprofessional", "Support Staff", "Other"
]

ALL_ROLES = [
    "student",
    "member",
    "staff",
    "teacher",
    "administrator",
    "principal",
    "high_rank",
    "developer",
]

ROLE_GROUPS = {
    "student":       "Students",
    "member":        "Students",
    "staff":         "Teachers",
    "teacher":       "Teachers",
    "administrator": "Admins",
    "principal":     "Admins",
    "high_rank":     "Admins",
    "developer":     "Admins",
}

ADMIN_PANEL_GROUPS = ["Admins", "Teachers", "Students"]

ROLE_LABELS = {
    "student":       "Student",
    "member":        "Member",
    "staff":         "Staff",
    "teacher":       "Teacher",
    "administrator": "Administrator",
    "principal":     "Principal",
    "high_rank":     "High Rank",
    "developer":     "Developer",
}

ROLE_BADGE_COLORS = {
    "student":       "secondary",
    "member":        "info",
    "staff":         "primary",
    "teacher":       "success",
    "administrator": "warning",
    "principal":     "orange",
    "high_rank":     "danger",
    "developer":     "dark",
}

DEFAULT_PERMISSIONS = {
    "student": {
        "can_join_class":        True,
        "can_create_class":      False,
        "can_issue_writeup":     False,
        "can_delete_writeup":    False,
        "can_view_all_writeups": False,
        "can_remove_student":    False,
        "can_access_admin":      False,
        "can_delete_user":       False,
        "can_change_roles":      False,
        "can_approve_users":     False,
    },
    "member": {
        "can_join_class":        True,
        "can_create_class":      False,
        "can_issue_writeup":     False,
        "can_delete_writeup":    False,
        "can_view_all_writeups": False,
        "can_remove_student":    False,
        "can_access_admin":      False,
        "can_delete_user":       False,
        "can_change_roles":      False,
        "can_approve_users":     False,
    },
    "staff": {
        "can_join_class":        True,
        "can_create_class":      False,
        "can_issue_writeup":     False,
        "can_delete_writeup":    False,
        "can_view_all_writeups": True,
        "can_remove_student":    False,
        "can_access_admin":      False,
        "can_delete_user":       False,
        "can_change_roles":      False,
        "can_approve_users":     False,
    },
    "teacher": {
        "can_join_class":        True,
        "can_create_class":      True,
        "can_issue_writeup":     True,
        "can_delete_writeup":    False,
        "can_view_all_writeups": True,
        "can_remove_student":    True,
        "can_access_admin":      False,
        "can_delete_user":       False,
        "can_change_roles":      False,
        "can_approve_users":     False,
    },
    "administrator": {
        "can_join_class":        True,
        "can_create_class":      True,
        "can_issue_writeup":     True,
        "can_delete_writeup":    True,
        "can_view_all_writeups": True,
        "can_remove_student":    True,
        "can_access_admin":      True,
        "can_delete_user":       True,
        "can_change_roles":      True,
        "can_approve_users":     True,
    },
    "principal": {
        "can_join_class":        True,
        "can_create_class":      True,
        "can_issue_writeup":     True,
        "can_delete_writeup":    True,
        "can_view_all_writeups": True,
        "can_remove_student":    True,
        "can_access_admin":      True,
        "can_delete_user":       True,
        "can_change_roles":      True,
        "can_approve_users":     True,
    },
    "high_rank": {
        "can_join_class":        True,
        "can_create_class":      True,
        "can_issue_writeup":     True,
        "can_delete_writeup":    True,
        "can_view_all_writeups": True,
        "can_remove_student":    True,
        "can_access_admin":      True,
        "can_delete_user":       True,
        "can_change_roles":      True,
        "can_approve_users":     True,
    },
    "developer": {
        "can_join_class":        True,
        "can_create_class":      True,
        "can_issue_writeup":     True,
        "can_delete_writeup":    True,
        "can_view_all_writeups": True,
        "can_remove_student":    True,
        "can_access_admin":      True,
        "can_delete_user":       True,
        "can_change_roles":      True,
        "can_approve_users":     True,
    },
}

PERMISSION_LABELS = {
    "can_join_class":        "Join Classes via Code",
    "can_create_class":      "Create Classes",
    "can_issue_writeup":     "Issue Write-Ups",
    "can_delete_writeup":    "Delete Write-Ups",
    "can_view_all_writeups": "View Any Student's Write-Ups",
    "can_remove_student":    "Remove Students from Classes",
    "can_access_admin":      "Access Admin Panel",
    "can_delete_user":       "Delete Users from System",
    "can_change_roles":      "Change User Roles",
    "can_approve_users":     "Approve / Reject New Users",
}


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def load_classes():
    if not os.path.exists(CLASSES_FILE):
        return {}
    with open(CLASSES_FILE) as f:
        return json.load(f)

def save_classes(c):
    with open(CLASSES_FILE, "w") as f:
        json.dump(c, f, indent=2)

def load_writeups():
    if not os.path.exists(WRITEUPS_FILE):
        return {}
    with open(WRITEUPS_FILE) as f:
        return json.load(f)

def save_writeups(w):
    with open(WRITEUPS_FILE, "w") as f:
        json.dump(w, f, indent=2)

def load_permissions():
    if not os.path.exists(PERMISSIONS_FILE):
        save_permissions(DEFAULT_PERMISSIONS)
        return DEFAULT_PERMISSIONS
    with open(PERMISSIONS_FILE) as f:
        stored = json.load(f)
    changed = False
    for role, defaults in DEFAULT_PERMISSIONS.items():
        stored.setdefault(role, {})
        for perm, val in defaults.items():
            if perm not in stored[role]:
                stored[role][perm] = val
                changed = True
    if changed:
        save_permissions(stored)
    return stored

def save_permissions(p):
    with open(PERMISSIONS_FILE, "w") as f:
        json.dump(p, f, indent=2)

def has_perm(role, perm):
    perms = load_permissions()
    return perms.get(role, {}).get(perm, False)

def role_perm(perm):
    return has_perm(session.get("role", "student"), perm)

def role_rank(role):
    try:
        return ALL_ROLES.index(role)
    except ValueError:
        return -1

def can_manage(actor_role, target_role):
    return role_rank(actor_role) > role_rank(target_role)

def default_role(user_type):
    return "student" if user_type == "student" else "member"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def fmt_date(iso_str):
    dt = parse_iso(iso_str)
    if not dt:
        return "Unknown"
    return dt.strftime("%b %d, %Y at %I:%M %p UTC")

def purge_expired_rejections():
    users  = load_users()
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    to_del = [e for e, u in users.items()
              if u.get("status") == "rejected"
              and (ts := parse_iso(u.get("rejected_at", "")))
              and ts < cutoff]
    for email in to_del:
        del users[email]
        writeups = load_writeups()
        if email in writeups:
            del writeups[email]
            save_writeups(writeups)
    if to_del:
        save_users(users)

def validate_nhps_email(email):
    email = email.strip().lower()
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        return False, f"Only @{ALLOWED_DOMAIN} addresses are allowed."
    local = email.split("@")[0]
    if STUDENT_PATTERN.match(local): return True, "student"
    if STAFF_PATTERN.match(local):   return True, "staff"
    return False, "Email must be a 6-digit student ID or firstname.lastname for staff."

def generate_class_code(classes):
    existing = {c["code"] for c in classes.values()}
    for _ in range(200):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in existing:
            return code
    raise RuntimeError("Could not generate a unique class code.")

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]

def unique_slug(base, classes, exclude_id=None):
    existing = {c["url_slug"] for cid, c in classes.items() if cid != exclude_id}
    slug = base or "class"
    candidate, n = slug, 2
    while candidate in existing:
        candidate = f"{slug}-{n}"; n += 1
    return candidate

def get_class_by_code(code, classes):
    code = code.strip().upper()
    for cid, c in classes.items():
        if c["code"] == code: return cid, c
    return None, None

def get_class_by_slug(slug, classes):
    for cid, c in classes.items():
        if c["url_slug"] == slug: return cid, c
    return None, None


def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "email" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return d

def approved_required(f):
    @wraps(f)
    def d(*a, **kw):
        users  = load_users()
        status = users.get(session.get("email", ""), {}).get("status", "pending")
        if status == "approved":
            session["status"] = "approved"
        if session.get("status") != "approved":
            flash("Your account is pending approval.", "info")
            return redirect(url_for("pending"))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if "email" not in session:
            flash("Please log in.", "info")
            return redirect(url_for("login"))
        if not role_perm("can_access_admin"):
            flash("Access denied.", "error")
            return redirect(url_for("dashboard"))
        return f(*a, **kw)
    return d


@app.context_processor
def inject_globals():
    return {
        "ROLE_LABELS":       ROLE_LABELS,
        "ROLE_BADGE_COLORS": ROLE_BADGE_COLORS,
        "ALL_ROLES":         ALL_ROLES,
        "ROLE_GROUPS":       ROLE_GROUPS,
        "role_perm":         role_perm,
        "fmt_date":          fmt_date,
        "session":           session,
    }


@app.route("/")
def index():
    purge_expired_rejections()
    return redirect(url_for("dashboard") if "email" in session else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "email" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        def re_render():
            return render_template("register.html", email=email,
                                   grade_choices=GRADE_CHOICES, staff_titles=STAFF_TITLES)

        valid, result = validate_nhps_email(email)
        if not valid: flash(result, "error"); return re_render()
        user_type = result

        if len(password) < 8: flash("Password must be at least 8 characters.", "error"); return re_render()
        if password != confirm: flash("Passwords do not match.", "error"); return re_render()

        users = load_users()
        if email in users: flash("An account with that email already exists.", "error"); return re_render()

        first_name = request.form.get("first_name", "").strip()
        last_name  = request.form.get("last_name", "").strip()
        if not first_name or not last_name:
            flash("First and last name are required.", "error"); return re_render()

        record = {
            "password_hash": generate_password_hash(password),
            "user_type":    user_type,
            "first_name":   first_name,
            "last_name":    last_name,
            "display_name": f"{first_name} {last_name}",
            "status":       "pending",
            "role":         default_role(user_type),
            "created_at":   now_iso(),
        }

        if user_type == "student":
            grade    = request.form.get("grade", "").strip()
            birthday = request.form.get("birthday", "").strip()
            if grade not in GRADE_CHOICES:
                flash("Please select a valid grade (7th or 8th).", "error"); return re_render()
            if not birthday:
                flash("Date of birth is required.", "error"); return re_render()
            record["grade"] = grade; record["birthday"] = birthday
        else:
            department = request.form.get("department", "").strip()
            title      = request.form.get("title", "").strip()
            if not department: flash("Department is required.", "error"); return re_render()
            if title not in STAFF_TITLES:
                flash("Please select a valid role/title.", "error"); return re_render()
            record["department"] = department; record["title"] = title

        users[email] = record
        save_users(users)
        flash("Account created! Pending approval by an administrator.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", email="",
                           grade_choices=GRADE_CHOICES, staff_titles=STAFF_TITLES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "email" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        users    = load_users()
        user     = users.get(email)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        if "role" not in user:
            user["role"] = default_role(user["user_type"])
            save_users(users)

        session.permanent       = True
        session["email"]        = email
        session["display_name"] = user["display_name"]
        session["user_type"]    = user["user_type"]
        session["status"]       = user.get("status", "pending")
        session["role"]         = user["role"]

        return redirect(url_for("pending") if session["status"] != "approved" else url_for("dashboard"))

    return render_template("login.html", email="")


@app.route("/pending")
@login_required
def pending():
    users  = load_users()
    status = users.get(session["email"], {}).get("status", "pending")
    if status == "approved":
        session["status"] = "approved"
        return redirect(url_for("dashboard"))
    if status == "rejected":
        session.clear()
        flash("Your registration was not approved. Please contact the school office.", "error")
        return redirect(url_for("login"))
    return render_template("pending.html", display_name=session["display_name"], email=session["email"])


@app.route("/dashboard")
@login_required
@approved_required
def dashboard():
    users = load_users()
    user  = users.get(session["email"], {})
    role  = user.get("role", default_role(user.get("user_type", "student")))
    session["role"] = role

    writeups        = load_writeups()
    my_writeups     = writeups.get(session["email"], [])
    writeup_count   = len(my_writeups)
    sorted_writeups = sorted(my_writeups, key=lambda w: w.get("date", ""), reverse=True)
    recent_writeups = sorted_writeups[:3]

    return render_template("dashboard.html",
                           email=session["email"],
                           display_name=session["display_name"],
                           user_type=session["user_type"],
                           role=role,
                           role_label=ROLE_LABELS.get(role, role.title()),
                           role_badge=ROLE_BADGE_COLORS.get(role, "secondary"),
                           user=user,
                           writeup_count=writeup_count,
                           recent_writeups=recent_writeups)


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("login"))


DEV_KEY   = "nhps-dev-2025"
DEV_EMAIL = "dev@nhps.net"

@app.route("/dev-login")
def dev_login():
    if request.args.get("key") != DEV_KEY:
        from flask import abort; abort(404)
    users = load_users()
    if DEV_EMAIL not in users:
        users[DEV_EMAIL] = {
            "password_hash": generate_password_hash(DEV_KEY + "-unused"),
            "user_type": "staff", "first_name": "Developer", "last_name": "Account",
            "display_name": "Developer Account", "status": "approved", "role": "developer",
            "department": "IT / Development", "title": "IT / Developer", "created_at": now_iso(),
        }
    users[DEV_EMAIL]["status"] = "approved"
    users[DEV_EMAIL]["role"]   = "developer"
    save_users(users)
    session.clear()
    session.permanent       = True
    session["email"]        = DEV_EMAIL
    session["display_name"] = users[DEV_EMAIL]["display_name"]
    session["user_type"]    = users[DEV_EMAIL]["user_type"]
    session["status"]       = "approved"
    session["role"]         = "developer"
    flash("Logged in as Developer.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin")
@admin_required
def admin():
    purge_expired_rejections()
    users      = load_users()
    writeups   = load_writeups()
    actor_role = session.get("role", "student")
    assignable = [r for r in ALL_ROLES if can_manage(actor_role, r)
                  and role_perm("can_change_roles")]
    now        = datetime.now(timezone.utc)

    def enrich(email, u):
        r = u.get("role", default_role(u.get("user_type", "student")))
        days_left = None
        if u.get("status") == "rejected":
            rejected_at = parse_iso(u.get("rejected_at", ""))
            if rejected_at:
                delta = (rejected_at + timedelta(days=3)) - now
                days_left = max(0, delta.days)
        return {
            **u,
            "email":         email,
            "role":          r,
            "role_label":    ROLE_LABELS.get(r, r.title()),
            "role_badge":    ROLE_BADGE_COLORS.get(r, "secondary"),
            "role_group":    ROLE_GROUPS.get(r, "Students"),
            "can_modify":    can_manage(actor_role, r),
            "writeup_count": len(writeups.get(email, [])),
            "days_left":     days_left,
        }

    all_users    = {e: enrich(e, u) for e, u in users.items()}
    pending_u    = {e: u for e, u in all_users.items() if u.get("status") == "pending"}
    rejected_u   = {e: u for e, u in all_users.items() if u.get("status") == "rejected"}
    approved_u   = {e: u for e, u in all_users.items() if u.get("status") == "approved"}

    grouped_approved = {}
    for group in ADMIN_PANEL_GROUPS:
        grouped_approved[group] = {e: u for e, u in approved_u.items()
                                   if u.get("role_group") == group}

    return render_template("admin.html",
        grouped_approved = grouped_approved,
        group_order      = ADMIN_PANEL_GROUPS,
        approved         = approved_u,
        pending          = pending_u,
        rejected         = rejected_u,
        current_email    = session["email"],
        actor_role       = actor_role,
        assignable_roles = assignable,
        role_labels      = ROLE_LABELS,
        role_badges      = ROLE_BADGE_COLORS,
        role_groups      = ROLE_GROUPS,
    )


@app.route("/admin/user-lookup")
@admin_required
def user_lookup():
    email   = request.args.get("email", "").strip().lower()
    users   = load_users()
    classes = load_classes()

    if not email or email not in users:
        return jsonify(ok=False, error="User not found.")

    user_classes = []
    for cid, c in classes.items():
        is_teacher = c.get("teacher_email") == email
        is_member  = email in c.get("members", [])
        if is_teacher or is_member:
            user_classes.append({
                "id":           cid,
                "name":         c.get("name", ""),
                "subject":      c.get("subject", ""),
                "period":       c.get("period", ""),
                "year":         c.get("year", ""),
                "code":         c.get("code", ""),
                "slug":         c.get("url_slug", ""),
                "is_teacher":   is_teacher,
                "member_count": len(c.get("members", [])),
            })

    return jsonify(ok=True, email=email, classes=user_classes)


@app.route("/admin/approve/<path:email>", methods=["POST"])
@admin_required
def approve_user(email):
    if not role_perm("can_approve_users"):
        flash("You don't have permission to approve users.", "error")
        return redirect(url_for("admin"))
    users = load_users()
    if email in users:
        users[email]["status"] = "approved"
        users[email].pop("rejected_at", None)
        save_users(users)
        flash(f"Approved {users[email]['display_name']}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/reject/<path:email>", methods=["POST"])
@admin_required
def reject_user(email):
    if not role_perm("can_approve_users"):
        flash("You don't have permission to reject users.", "error")
        return redirect(url_for("admin"))
    users = load_users()
    if email in users:
        users[email]["status"]      = "rejected"
        users[email]["rejected_at"] = now_iso()
        save_users(users)
        flash(f"Rejected {users[email]['display_name']}. Account deleted in 3 days.", "info")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<path:email>", methods=["POST"])
@admin_required
def delete_user(email):
    if not role_perm("can_delete_user"):
        flash("You don't have permission to delete users.", "error")
        return redirect(url_for("admin"))

    actor_role = session.get("role", "student")
    users      = load_users()

    if email not in users:
        flash("User not found.", "error"); return redirect(url_for("admin"))
    if email == session["email"]:
        flash("You cannot delete your own account.", "error"); return redirect(url_for("admin"))

    target_role = users[email].get("role", default_role(users[email].get("user_type", "student")))
    if not can_manage(actor_role, target_role):
        flash(f"You don't have permission to delete {users[email]['display_name']}.", "error")
        return redirect(url_for("admin"))

    display = users[email]["display_name"]
    del users[email]
    save_users(users)

    classes = load_classes()
    changed = False
    for cid, c in classes.items():
        if email in c.get("members", []):
            c["members"].remove(email); changed = True
        if c.get("teacher_email") == email:
            c["teacher_email"] = ""; c["teacher_name"] = "[Deleted]"; changed = True
    if changed:
        save_classes(classes)

    writeups = load_writeups()
    if email in writeups:
        del writeups[email]; save_writeups(writeups)

    flash(f'"{display}" has been permanently removed from the system.', "success")
    return redirect(url_for("admin"))


@app.route("/admin/set_role/<path:email>", methods=["POST"])
@admin_required
def set_role(email):
    if not role_perm("can_change_roles"):
        flash("You don't have permission to change roles.", "error")
        return redirect(url_for("admin"))

    new_role   = request.form.get("role", "").strip()
    actor_role = session.get("role", "student")
    users      = load_users()

    if email not in users:
        flash("User not found.", "error"); return redirect(url_for("admin"))
    if email == session["email"]:
        flash("You cannot change your own role.", "error"); return redirect(url_for("admin"))
    if new_role not in ALL_ROLES:
        flash("Invalid role selected.", "error"); return redirect(url_for("admin"))

    target_current_role = users[email].get("role", default_role(users[email].get("user_type", "student")))

    if not can_manage(actor_role, new_role):
        flash(f"You can't assign the '{ROLE_LABELS.get(new_role)}' role.", "error")
        return redirect(url_for("admin"))
    if not can_manage(actor_role, target_current_role):
        flash(f"You can't modify {users[email]['display_name']}'s role.", "error")
        return redirect(url_for("admin"))

    users[email]["role"] = new_role
    save_users(users)
    flash(f"Role updated to '{ROLE_LABELS.get(new_role)}' for {users[email]['display_name']}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/permissions")
@admin_required
def permissions_editor():
    if session.get("role") != "developer":
        flash("Only the Developer can edit role permissions.", "error")
        return redirect(url_for("admin"))
    perms = load_permissions()
    return render_template("permissions.html",
                           perms=perms,
                           all_roles=ALL_ROLES,
                           role_labels=ROLE_LABELS,
                           perm_labels=PERMISSION_LABELS)


@app.route("/admin/permissions/save", methods=["POST"])
@admin_required
def save_permissions_route():
    if session.get("role") != "developer":
        flash("Only the Developer can edit role permissions.", "error")
        return redirect(url_for("admin"))

    perms = load_permissions()
    for role in ALL_ROLES:
        for perm in PERMISSION_LABELS:
            perms[role][perm] = f"{role}_{perm}" in request.form

    for perm in PERMISSION_LABELS:
        perms["developer"][perm] = True

    save_permissions(perms)
    flash("Permissions updated successfully.", "success")
    return redirect(url_for("permissions_editor"))


@app.route("/admin/permissions/reset", methods=["POST"])
@admin_required
def reset_permissions():
    if session.get("role") != "developer":
        flash("Only the Developer can reset permissions.", "error")
        return redirect(url_for("admin"))
    save_permissions(DEFAULT_PERMISSIONS)
    flash("Permissions reset to defaults.", "info")
    return redirect(url_for("permissions_editor"))


@app.route("/writeups/<path:student_email>")
@login_required
@approved_required
def view_writeups(student_email):
    email        = session["email"]
    is_self      = email == student_email
    can_view_all = role_perm("can_view_all_writeups")

    if not is_self and not can_view_all:
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))

    users    = load_users()
    writeups = load_writeups()
    student  = users.get(student_email)

    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin") if can_view_all else url_for("dashboard"))

    student_writeups = sorted(
        writeups.get(student_email, []),
        key=lambda w: w.get("date", ""),
        reverse=True
    )

    return render_template("writeups.html",
                           student=student,
                           student_email=student_email,
                           writeups=student_writeups,
                           can_issue=role_perm("can_issue_writeup"),
                           can_delete=role_perm("can_delete_writeup"))


@app.route("/writeups/<path:student_email>/add", methods=["POST"])
@login_required
@approved_required
def add_writeup(student_email):
    if not role_perm("can_issue_writeup"):
        flash("You don't have permission to issue write-ups.", "error")
        return redirect(url_for("dashboard"))

    title       = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()

    if not title or not description:
        flash("Write-up title and description are required.", "error")
        return redirect(url_for("view_writeups", student_email=student_email))

    users = load_users()
    if student_email not in users:
        flash("Student not found.", "error"); return redirect(url_for("admin"))

    writeups = load_writeups()
    writeups.setdefault(student_email, []).append({
        "id":          str(uuid.uuid4()),
        "title":       title,
        "description": description,
        "date":        now_iso(),
        "issued_by":   session["email"],
        "issuer_name": session["display_name"],
    })
    save_writeups(writeups)
    flash(f"Write-up added for {users[student_email]['display_name']}.", "success")
    return redirect(url_for("view_writeups", student_email=student_email))


@app.route("/writeups/<path:student_email>/delete/<writeup_id>", methods=["POST"])
@login_required
@approved_required
def delete_writeup(student_email, writeup_id):
    if not role_perm("can_delete_writeup"):
        flash("You don't have permission to delete write-ups.", "error")
        return redirect(url_for("view_writeups", student_email=student_email))

    writeups = load_writeups()
    before   = writeups.get(student_email, [])
    after    = [w for w in before if w["id"] != writeup_id]

    if len(before) == len(after):
        flash("Write-up not found.", "error")
    else:
        writeups[student_email] = after
        save_writeups(writeups)
        flash("Write-up deleted.", "info")

    return redirect(url_for("view_writeups", student_email=student_email))


@app.route("/classes")
@login_required
@approved_required
def classrooms():
    email   = session["email"]
    role    = session.get("role", "student")
    classes = load_classes()

    if role_perm("can_create_class"):
        my = [{**c, "id": cid, "member_count": len(c.get("members", []))}
              for cid, c in classes.items() if c.get("teacher_email") == email]
    else:
        my = [{**c, "id": cid, "member_count": len(c.get("members", []))}
              for cid, c in classes.items() if email in c.get("members", [])]

    return render_template("classrooms.html",
                           teaching=my,
                           user_type=session["user_type"],
                           role=role,
                           display_name=session["display_name"],
                           can_create=role_perm("can_create_class"),
                           can_join=role_perm("can_join_class"))


@app.route("/classes/create", methods=["POST"])
@login_required
@approved_required
def create_class():
    if not role_perm("can_create_class"):
        flash("You don't have permission to create classes.", "error")
        return redirect(url_for("classrooms"))

    name     = request.form.get("name", "").strip()
    subject  = request.form.get("subject", "").strip()
    period   = request.form.get("period", "").strip() or "—"
    year     = request.form.get("year", "").strip() or "2025–2026"
    slug_raw = request.form.get("url_slug", "").strip()

    if not name or not subject:
        flash("Class name and subject are required.", "error")
        return redirect(url_for("classrooms"))

    classes  = load_classes()
    users    = load_users()
    teacher  = users.get(session["email"], {})
    code     = generate_class_code(classes)
    slug     = unique_slug(slugify(slug_raw if slug_raw else name), classes)
    class_id = str(uuid.uuid4())

    classes[class_id] = {
        "id": class_id, "name": name, "subject": subject,
        "period": period, "year": year, "code": code, "url_slug": slug,
        "teacher_email": session["email"],
        "teacher_name":  teacher.get("display_name", session["email"]),
        "members": [],
    }
    save_classes(classes)
    flash(f'Class "{name}" created! Code: {code}', "success")
    return redirect(url_for("view_classroom", slug=slug))


@app.route("/c/<slug>")
@login_required
@approved_required
def view_classroom(slug):
    classes = load_classes()
    users   = load_users()
    cid, classroom = get_class_by_slug(slug, classes)

    if not classroom:
        flash("Classroom not found.", "error")
        return redirect(url_for("classrooms"))

    email      = session["email"]
    is_teacher = classroom["teacher_email"] == email or role_perm("can_access_admin")
    is_member  = email in classroom.get("members", [])

    if not is_teacher and not is_member:
        flash("You are not enrolled in this class.", "error")
        return redirect(url_for("classrooms"))

    writeups = load_writeups()
    members  = []
    for m in classroom.get("members", []):
        u = users.get(m, {})
        r = u.get("role", "student")
        members.append({
            "email":         m,
            "display_name":  u.get("display_name", m),
            "role":          r,
            "role_label":    ROLE_LABELS.get(r, "Student"),
            "role_badge":    ROLE_BADGE_COLORS.get(r, "secondary"),
            "writeup_count": len(writeups.get(m, [])),
        })

    return render_template("classroom.html",
                           classroom={**classroom, "id": cid},
                           members=members,
                           is_teacher=is_teacher,
                           can_remove=role_perm("can_remove_student"),
                           can_issue_writeup=role_perm("can_issue_writeup"),
                           can_view_writeups=role_perm("can_view_all_writeups"))


@app.route("/classes/join", methods=["POST"])
@login_required
@approved_required
def join_class():
    if not role_perm("can_join_class"):
        flash("You don't have permission to join classes.", "error")
        return redirect(url_for("classrooms"))

    email = session["email"]
    code  = request.form.get("code", "").strip().upper()

    if not code:
        flash("Please enter a class code.", "error")
        return redirect(url_for("classrooms"))

    classes = load_classes()
    cid, classroom = get_class_by_code(code, classes)

    if not classroom:
        flash(f'No class found with code "{code}".', "error")
        return redirect(url_for("classrooms"))

    if email in classroom.get("members", []) or classroom.get("teacher_email") == email:
        flash("You're already in this class!", "info")
        return redirect(url_for("view_classroom", slug=classroom["url_slug"]))

    classes[cid].setdefault("members", []).append(email)
    save_classes(classes)
    flash(f'Joined "{classroom["name"]}"!', "success")
    return redirect(url_for("view_classroom", slug=classroom["url_slug"]))


@app.route("/classes/<class_id>/remove", methods=["POST"])
@login_required
@approved_required
def remove_student(class_id):
    classes   = load_classes()
    classroom = classes.get(class_id)

    if not classroom:
        flash("Classroom not found.", "error")
        return redirect(url_for("classrooms"))

    is_teacher = classroom["teacher_email"] == session["email"]
    can_remove = role_perm("can_remove_student")

    if not is_teacher and not can_remove:
        flash("You don't have permission to remove students.", "error")
        return redirect(url_for("view_classroom", slug=classroom["url_slug"]))

    student_email = request.form.get("student_email", "")
    if student_email in classroom.get("members", []):
        classroom["members"].remove(student_email)
        save_classes(classes)
        flash("Student removed.", "info")
    else:
        flash("Student not found in this class.", "error")

    return redirect(url_for("view_classroom", slug=classroom["url_slug"]))


if __name__ == "__main__":
    app.run(debug=True)