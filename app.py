from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfMerger
import os
import docx2txt
from PIL import Image
import pdf2docx
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret'

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)


# === Database Setup ===
def init_db():
    with sqlite3.connect('db.sqlite3') as con:
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT
                    )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        action TEXT,
                        filename TEXT
                    )''')
        con.commit()


init_db()


# === Routes ===
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('db.sqlite3') as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = cur.fetchone()
            if user:
                session['user_id'] = user[0]
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            with sqlite3.connect('db.sqlite3') as con:
                cur = con.cursor()
                cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                con.commit()
                flash('Registration successful! Please log in.')
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose another.')
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/convert/pdf-to-doc', methods=['POST'])
def pdf_to_doc():
    if 'file' not in request.files:
        flash('No file uploaded.')
        return redirect(url_for('dashboard'))

    pdf = request.files['file']
    filename = secure_filename(pdf.filename)
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join(RESULT_FOLDER, filename.replace('.pdf', '.docx'))
    pdf.save(input_path)

    pdf2docx.parse(pdf_file=input_path, docx_file=output_path)
    log_history('PDF to DOC', output_path)
    return send_file(output_path, as_attachment=True)


@app.route('/convert/doc-to-txt', methods=['POST'])
def doc_to_txt():
    doc = request.files['file']
    filename = secure_filename(doc.filename)
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join(RESULT_FOLDER, filename.replace('.docx', '.txt'))
    doc.save(input_path)

    text = docx2txt.process(input_path)
    with open(output_path, 'w') as f:
        f.write(text)

    log_history('DOC to TXT', output_path)
    return send_file(output_path, as_attachment=True)


@app.route('/convert/img-to-jpg', methods=['POST'])
def img_to_jpg():
    img = request.files['file']
    filename = secure_filename(img.filename)
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_path = os.path.join(RESULT_FOLDER, filename.rsplit('.', 1)[0] + '.jpg')
    img.save(input_path)

    image = Image.open(input_path)
    rgb_im = image.convert('RGB')
    rgb_im.save(output_path, format='JPEG')

    log_history('Image to JPG', output_path)
    return send_file(output_path, as_attachment=True)


@app.route('/merge/pdf', methods=['POST'])
def merge_pdf():
    files = request.files.getlist('files')
    if not files or len(files) < 2:
        flash("Please select at least 2 PDF files to merge.")
        return redirect(url_for('dashboard'))

    merger = PdfMerger()
    saved_files = []

    for f in files:
        if f and f.filename.lower().endswith('.pdf'):
            path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
            f.save(path)
            saved_files.append(path)
            merger.append(path)

    if not saved_files:
        flash("No valid PDF files were uploaded.")
        return redirect(url_for('dashboard'))

    output_path = os.path.join(RESULT_FOLDER, 'merged.pdf')
    merger.write(output_path)
    merger.close()

    log_history('PDF Merge', output_path)
    return send_file(output_path, as_attachment=True)


@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect('db.sqlite3') as con:
        cur = con.cursor()
        cur.execute("SELECT action, filename FROM history WHERE user_id=?", (session['user_id'],))
        logs = cur.fetchall()
    return render_template('history.html', logs=logs)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# === Logging Helper ===
def log_history(action, filename):
    if 'user_id' in session:
        with sqlite3.connect('db.sqlite3') as con:
            cur = con.cursor()
            cur.execute("INSERT INTO history (user_id, action, filename) VALUES (?, ?, ?)",
                        (session['user_id'], action, os.path.basename(filename)))
            con.commit()


if __name__ == '__main__':
    app.run(debug=True)
