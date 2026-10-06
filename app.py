from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory
)

from database import create_tables, get_db_connection

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import os
import uuid


app = Flask(__name__)

app.secret_key = "noteswap_campus_secret_key"


# =========================================================
# UPLOAD SETTINGS
# =========================================================

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

create_tables()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def login_required():

    return "user_id" in session


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() == "pdf"
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()

        email = request.form["email"].strip().lower()

        password = request.form["password"]


        connection = get_db_connection()


        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()


        if existing_user:

            connection.close()

            return render_template(
                "register.html",
                error="Email already registered!"
            )


        hashed_password = generate_password_hash(
            password
        )


        connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password
            )

            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password
            )
        )


        connection.commit()

        connection.close()


        return redirect("/login")


    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        password = request.form["password"]


        connection = get_db_connection()


        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()


        connection.close()


        if user:

            password_valid = False


            try:

                password_valid = check_password_hash(
                    user["password"],
                    password
                )

            except Exception:

                password_valid = False


            # Support old accounts
            if not password_valid:

                if user["password"] == password:

                    password_valid = True


                    connection = get_db_connection()


                    connection.execute(
                        """
                        UPDATE users

                        SET password = ?

                        WHERE id = ?
                        """,
                        (
                            generate_password_hash(password),
                            user["id"]
                        )
                    )


                    connection.commit()

                    connection.close()


            if password_valid:

                session["user_id"] = user["id"]

                session["user_name"] = user["name"]

                session["user_email"] = user["email"]


                return redirect("/dashboard")


        return render_template(
            "login.html",
            error="Invalid email or password!"
        )


    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    note_count = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM notes
        """
    ).fetchone()["total"]


    favorite_count = connection.execute(
        """
        SELECT COUNT(*) AS total

        FROM favorites

        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()["total"]


    upload_count = connection.execute(
        """
        SELECT COUNT(*) AS total

        FROM notes

        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()["total"]


    recent_notes = connection.execute(
        """
        SELECT
            notes.*,
            users.name

        FROM notes

        JOIN users
        ON notes.user_id = users.id

        ORDER BY notes.created_at DESC

        LIMIT 4
        """
    ).fetchall()


    connection.close()


    return render_template(
        "dashboard.html",
        note_count=note_count,
        favorite_count=favorite_count,
        upload_count=upload_count,
        recent_notes=recent_notes
    )


# =========================================================
# NOTES
# =========================================================

@app.route("/notes")
def notes():

    if not login_required():

        return redirect("/login")


    search = request.args.get(
        "search",
        ""
    ).strip()


    connection = get_db_connection()


    if search:

        notes_data = connection.execute(
            """
            SELECT
                notes.*,
                users.name

            FROM notes

            JOIN users
            ON notes.user_id = users.id

            WHERE
                notes.title LIKE ?
                OR notes.subject LIKE ?
                OR notes.description LIKE ?

            ORDER BY notes.created_at DESC
            """,
            (
                "%" + search + "%",
                "%" + search + "%",
                "%" + search + "%"
            )
        ).fetchall()

    else:

        notes_data = connection.execute(
            """
            SELECT
                notes.*,
                users.name

            FROM notes

            JOIN users
            ON notes.user_id = users.id

            ORDER BY notes.created_at DESC
            """
        ).fetchall()


    connection.close()


    return render_template(
        "notes.html",
        notes=notes_data,
        search=search
    )


# =========================================================
# UPLOAD PAGE
# =========================================================

@app.route("/upload")
def upload():

    if not login_required():

        return redirect("/login")


    return render_template("upload.html")


# =========================================================
# UPLOAD PDF
# =========================================================

@app.route("/upload", methods=["POST"])
def upload_note():

    if not login_required():

        return redirect("/login")


    title = request.form["title"].strip()

    subject = request.form["subject"].strip()

    description = request.form["description"].strip()


    file = request.files.get("file")


    if not file or file.filename == "":

        return render_template(
            "upload.html",
            error="Please select a PDF file."
        )


    if not allowed_file(file.filename):

        return render_template(
            "upload.html",
            error="Only PDF files are allowed."
        )


    original_filename = secure_filename(
        file.filename
    )


    # Create unique filename
    unique_filename = (
        str(uuid.uuid4())
        + "_"
        + original_filename
    )


    # Save PDF
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename
    )


    file.save(file_path)


    # Save information in database
    connection = get_db_connection()


    connection.execute(
        """
        INSERT INTO notes
        (
            title,
            subject,
            description,
            filename,
            user_id
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            title,
            subject,
            description,
            unique_filename,
            session["user_id"]
        )
    )


    connection.commit()

    connection.close()


    return redirect("/notes")


# =========================================================
# OPEN PDF
# =========================================================

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):

    if not login_required():

        return redirect("/login")


    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        mimetype="application/pdf",
        as_attachment=False
    )


# =========================================================
# FAVORITE / UNFAVORITE
# =========================================================

@app.route(
    "/favorite/<int:note_id>",
    methods=["POST"]
)
def toggle_favorite(note_id):

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    existing = connection.execute(
        """
        SELECT id

        FROM favorites

        WHERE user_id = ?
        AND note_id = ?
        """,
        (
            session["user_id"],
            note_id
        )
    ).fetchone()


    if existing:

        connection.execute(
            """
            DELETE FROM favorites

            WHERE user_id = ?
            AND note_id = ?
            """,
            (
                session["user_id"],
                note_id
            )
        )

    else:

        connection.execute(
            """
            INSERT INTO favorites
            (
                user_id,
                note_id
            )

            VALUES (?, ?)
            """,
            (
                session["user_id"],
                note_id
            )
        )


    connection.commit()

    connection.close()


    return redirect(
        request.referrer or "/notes"
    )


# =========================================================
# FAVORITES
# =========================================================

@app.route("/favorites")
def favorites():

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    favorite_notes = connection.execute(
        """
        SELECT
            notes.*,
            users.name

        FROM favorites

        JOIN notes
        ON favorites.note_id = notes.id

        JOIN users
        ON notes.user_id = users.id

        WHERE favorites.user_id = ?

        ORDER BY notes.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()


    connection.close()


    return render_template(
        "favorites.html",
        notes=favorite_notes
    )


# =========================================================
# MY UPLOADS
# =========================================================

@app.route("/my-uploads")
def my_uploads():

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    uploads = connection.execute(
        """
        SELECT *

        FROM notes

        WHERE user_id = ?

        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()


    connection.close()


    return render_template(
        "my_uploads.html",
        notes=uploads
    )


# =========================================================
# DELETE NOTE
# =========================================================

@app.route(
    "/delete-note/<int:note_id>",
    methods=["POST"]
)
def delete_note(note_id):

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    note = connection.execute(
        """
        SELECT *

        FROM notes

        WHERE id = ?
        AND user_id = ?
        """,
        (
            note_id,
            session["user_id"]
        )
    ).fetchone()


    if note:

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            note["filename"]
        )


        if os.path.exists(file_path):

            os.remove(file_path)


        connection.execute(
            """
            DELETE FROM notes

            WHERE id = ?
            AND user_id = ?
            """,
            (
                note_id,
                session["user_id"]
            )
        )


        connection.commit()


    connection.close()


    return redirect("/my-uploads")


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if not login_required():

        return redirect("/login")


    connection = get_db_connection()


    user = connection.execute(
        """
        SELECT *

        FROM users

        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()


    connection.close()


    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)