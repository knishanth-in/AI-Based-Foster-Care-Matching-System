from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# -------------------- SAFE INT --------------------
def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

# -------------------- DATABASE --------------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS child(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        gender TEXT,
        behavior TEXT,
        location_type TEXT,
        needs TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS family(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        language TEXT,
        environment TEXT,
        parenting TEXT,
        special_support TEXT,
        min_age INTEGER,
        max_age INTEGER,
        location_type TEXT,
        preferred_behavior TEXT,
        support_type TEXT,
        capacity INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# -------------------- GET DATA --------------------
def get_all_data():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM child")
    children = [dict(row) for row in c.fetchall()]

    c.execute("SELECT * FROM family")
    families = [dict(row) for row in c.fetchall()]

    conn.close()
    return children, families

# -------------------- MATCHING --------------------
def match_with_reason(child, family):
    score = 0
    reasons = []

    age = safe_int(child.get('age'))
    behavior = (child.get('behavior') or "").lower()
    location = (child.get('location_type') or "").lower()
    needs = (child.get('needs') or "").lower()

    min_age = safe_int(family.get('min_age'))
    max_age = safe_int(family.get('max_age'), 100)
    capacity = safe_int(family.get('capacity'), 1)

    if capacity <= 0:
        return 0, ["No capacity"]

    if min_age <= age <= max_age:
        score += 25
        reasons.append("Age match")

    if location == (family.get('location_type') or "").lower():
        score += 20
        reasons.append("Location match")

    if (family.get('preferred_behavior') or "any").lower() in [behavior, "any"]:
        score += 20
        reasons.append("Behavior match")

    if needs == (family.get('support_type') or "").lower():
        score += 25
        reasons.append("Support match")

    return score, reasons

def get_label(score):
    if score >= 70:
        return "Highly Compatible"
    elif score >= 40:
        return "Moderate"
    else:
        return "Low"

def find_matches(child, families):
    results = []
    for family in families:
        score, reasons = match_with_reason(child, family)
        results.append({
            "family": family.get('name') or "Unknown",
            "score": score,
            "label": get_label(score),
            "reasons": reasons
        })
    return sorted(results, key=lambda x: x['score'], reverse=True)[:3]

# -------------------- ROUTES --------------------
@app.route('/')
def home():
    return render_template("index.html")

# ---------- ADMIN LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == "IamAdmin":
            session['admin'] = True
            return redirect('/admin')
        else:
            error = "Incorrect password"
    return render_template("login.html", error=error)

# ---------- USER REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            error = "All fields required"
        else:
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            try:
                c.execute("INSERT INTO user (username, password) VALUES (?, ?)",
                          (username, generate_password_hash(password)))
                conn.commit()
                return redirect('/user_login')
            except:
                error = "User already exists"
            conn.close()

    return render_template("register.html", error=error)

# ---------- USER LOGIN ----------
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    error = None
    if request.method == 'POST':
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT password FROM user WHERE username=?",
                  (request.form.get('username'),))
        result = c.fetchone()
        conn.close()

        if result and check_password_hash(result[0], request.form.get('password')):
            session['user'] = request.form.get('username')
            return redirect('/dashboard')
        else:
            error = "Invalid credentials"

    return render_template("user_login.html", error=error)

# ---------- USER LOGOUT ----------
@app.route('/user_logout')
def user_logout():
    session.pop('user', None)
    return redirect('/user_login')

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    if not session.get('user'):
        return redirect('/user_login')

    children, families = get_all_data()
    return render_template("dashboard.html",
                           username=session['user'],
                           total_children=len(children),
                           total_families=len(families))

# ---------- ADD CHILD ----------
@app.route('/add_child', methods=['GET', 'POST'])
def add_child():
    if not session.get('user'):
        return redirect('/user_login')

    if request.method == 'POST':
        name = request.form.get('name')
        age = safe_int(request.form.get('age'))

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM child WHERE name=? AND age=?", (name, age))
        if c.fetchone():
            conn.close()
            return "Duplicate child entry!"

        c.execute("""INSERT INTO child 
        (name, age, gender, behavior, location_type, needs)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (name, age,
         request.form.get('gender'),
         request.form.get('behavior'),
         request.form.get('location_type'),
         request.form.get('needs')))

        conn.commit()
        conn.close()
        return redirect('/matches')

    return render_template("add_child.html")

# ---------- ADD FAMILY ----------
@app.route('/add_family', methods=['GET', 'POST'])
def add_family():
    if not session.get('user'):
        return redirect('/user_login')

    if request.method == 'POST':
        name = request.form.get('name')

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM family WHERE name=?", (name,))
        if c.fetchone():
            conn.close()
            return "Duplicate family entry!"

        c.execute("""INSERT INTO family 
        (name, language, environment, parenting, special_support,
         min_age, max_age, location_type, preferred_behavior, support_type, capacity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            request.form.get('language'),
            request.form.get('environment'),
            request.form.get('parenting'),
            request.form.get('special_support'),
            safe_int(request.form.get('min_age')),
            safe_int(request.form.get('max_age'), 100),
            request.form.get('location_type'),
            request.form.get('preferred_behavior'),
            request.form.get('support_type'),
            safe_int(request.form.get('capacity'), 1)
        ))

        conn.commit()
        conn.close()
        return redirect('/matches')

    return render_template("add_family.html")

# ---------- EDIT CHILD ----------
@app.route('/edit_child/<int:id>', methods=['GET', 'POST'])
def edit_child(id):
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        c.execute("""UPDATE child SET name=?, age=?, gender=?, behavior=?, location_type=?, needs=? WHERE id=?""",
                  (request.form.get('name'),
                   safe_int(request.form.get('age')),
                   request.form.get('gender'),
                   request.form.get('behavior'),
                   request.form.get('location_type'),
                   request.form.get('needs'),
                   id))
        conn.commit()
        conn.close()
        return redirect('/admin')

    c.execute("SELECT * FROM child WHERE id=?", (id,))
    child = c.fetchone()
    conn.close()

    return render_template("edit_child.html", child=child)

# ---------- EDIT FAMILY (ADDED) ----------
@app.route('/edit_family/<int:id>', methods=['GET', 'POST'])
def edit_family(id):
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        c.execute("""UPDATE family SET 
            name=?, language=?, environment=?, parenting=?, special_support=?,
            min_age=?, max_age=?, location_type=?, preferred_behavior=?, support_type=?, capacity=?
            WHERE id=?""",
        (
            request.form.get('name'),
            request.form.get('language'),
            request.form.get('environment'),
            request.form.get('parenting'),
            request.form.get('special_support'),
            safe_int(request.form.get('min_age')),
            safe_int(request.form.get('max_age')),
            request.form.get('location_type'),
            request.form.get('preferred_behavior'),
            request.form.get('support_type'),
            safe_int(request.form.get('capacity')),
            id
        ))
        conn.commit()
        conn.close()
        return redirect('/admin')

    c.execute("SELECT * FROM family WHERE id=?", (id,))
    family = c.fetchone()
    conn.close()

    return render_template("edit_family.html", family=family)

# ---------- DELETE CHILD ----------
@app.route('/delete_child/<int:id>')
def delete_child(id):
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM child WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

# ---------- DELETE FAMILY ----------
@app.route('/delete_family/<int:id>')
def delete_family(id):
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM family WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

# ---------- SEARCH (ADDED) ----------
@app.route('/search')
def search():
    if not session.get('user'):
        return redirect('/user_login')

    children, families = get_all_data()

    query = request.args.get('query', '').lower()

    filtered_children = []
    filtered_families = []

    if query:
        for child in children:
            if query in (child.get('name') or '').lower():
                filtered_children.append(child)

        for family in families:
            if query in (family.get('name') or '').lower():
                filtered_families.append(family)

    return render_template("search.html",
                           children=filtered_children,
                           families=filtered_families,
                           query=query)

# ---------- MATCHES ----------
@app.route('/matches')
def matches():
    if not session.get('user'):
        return redirect('/user_login')

    children, families = get_all_data()
    results = []

    for child in children:
        results.append({
            "child": child,
            "matches": find_matches(child, families)
        })

    return render_template("matches.html", results=results)

# ---------- ADMIN ----------
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/login')

    children, families = get_all_data()
    return render_template("admin.html", children=children, families=families)

# ---------- ADMIN LOGOUT ----------
@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')

# --------------------
if __name__ == '__main__':
    app.run(debug=True)