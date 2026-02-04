from flask import Flask, render_template, redirect, request, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.utils import secure_filename
from datetime import date, datetime, timedelta
import os
import shutil

# ===== PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


# ======================================================
# CONFIG
# ======================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = '123456'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ======================================================
# MODELOS
# ======================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(50))


# ---------- GRADO ----------
class Grado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50))

    secciones = db.relationship("Seccion", backref="grado", cascade="all, delete")


# ---------- SECCION ----------
class Seccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(10))
    grado_id = db.Column(db.Integer, db.ForeignKey('grado.id'))

    alumnos = db.relationship("Alumno", backref="seccion", cascade="all, delete")


# ---------- ALUMNO ----------
class Alumno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    dni = db.Column(db.String(15))
    foto = db.Column(db.String(200))
    seccion_id = db.Column(db.Integer, db.ForeignKey('seccion.id'))


# ---------- ASISTENCIA ----------
class Asistencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date)
    estado = db.Column(db.String(1))
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumno.id'))
    alumno = db.relationship("Alumno")


# ---------- PLANIFICACION ----------
class Curso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))


class Competencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200))
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'))

    capacidades = db.relationship('Capacidad', backref='competencia', cascade="all,delete")


class Capacidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200))
    competencia_id = db.Column(db.Integer, db.ForeignKey('competencia.id'))


# ======================================================
# LOGIN
# ======================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["user"]).first()

        if u and u.password == request.form["pass"]:
            login_user(u)
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


# ======================================================
# DASHBOARD
# ======================================================

@app.route("/dashboard")
@login_required
def dashboard():

    total_alumnos = Alumno.query.count()
    total_cursos = Curso.query.count()
    total_comp = Competencia.query.count()
    total_cap = Capacidad.query.count()

    os.makedirs("backups", exist_ok=True)
    backups = sorted(os.listdir("backups"), reverse=True)

    return render_template(
        "dashboard.html",
        total_alumnos=total_alumnos,
        total_cursos=total_cursos,
        total_comp=total_comp,
        total_cap=total_cap,
        backups=backups
    )


# ======================================================
# GRADOS
# ======================================================

@app.route("/grados", methods=["GET", "POST"])
@login_required
def grados():

    if request.method == "POST":
        db.session.add(Grado(nombre=request.form["nombre"]))
        db.session.commit()

    return render_template("grados.html", grados=Grado.query.all())

# ======================================================
# ASISTENCIA
# ======================================================

@app.route("/asistencia", methods=["GET", "POST"])
@login_required
def asistencia():

    hoy = date.today()

    grado_id = request.args.get("grado", type=int)
    seccion_id = request.args.get("seccion", type=int)

    grados = Grado.query.all()
    secciones = []
    alumnos = []

    if grado_id:
        secciones = Seccion.query.filter_by(grado_id=grado_id).all()

    if seccion_id:
        alumnos = Alumno.query.filter_by(seccion_id=seccion_id).all()

    if request.method == "POST":
        for a in alumnos:
            estado = request.form.get(str(a.id))

            db.session.add(
                Asistencia(
                    fecha=hoy,
                    estado=estado,
                    alumno_id=a.id
                )
            )

        db.session.commit()
        flash("Asistencia guardada", "success")
        return redirect(request.url)

    return render_template(
        "asistencia.html",
        hoy=hoy,
        grados=grados,
        secciones=secciones,
        alumnos=alumnos,
        grado_id=grado_id,
        seccion_id=seccion_id
    )


# ======================================================
# REPORTE WEB
# ======================================================

@app.route("/reporte")
@login_required
def reporte():

    fecha_base = request.args.get("fecha")
    tipo = request.args.get("tipo", "dia")

    grado_id = request.args.get("grado", type=int)
    seccion_id = request.args.get("seccion", type=int)
    dni = request.args.get("dni", "")

    if fecha_base:
        base = datetime.strptime(fecha_base, "%Y-%m-%d").date()
    else:
        base = date.today()

    # ===== calcular rango fechas
    if tipo == "dia":
        inicio = fin = base
    elif tipo == "semana":
        inicio = base - timedelta(days=base.weekday())
        fin = inicio + timedelta(days=6)
    elif tipo == "mes":
        inicio = base.replace(day=1)
        fin = base
    else:
        inicio = base.replace(month=1, day=1)
        fin = base

    grados = Grado.query.all()
    secciones = []
    alumnos_ids = []

    if grado_id:
        secciones = Seccion.query.filter_by(grado_id=grado_id).all()

    if seccion_id:
        alumnos_ids = [a.id for a in Alumno.query.filter_by(seccion_id=seccion_id).all()]

    query = Asistencia.query.filter(Asistencia.fecha.between(inicio, fin))

    if alumnos_ids:
        query = query.filter(Asistencia.alumno_id.in_(alumnos_ids))

    if dni:
        query = query.join(Alumno).filter(Alumno.dni.contains(dni))

    registros = query.order_by(Asistencia.fecha.desc()).all()

    return render_template(
        "reporte.html",
        registros=registros,
        inicio=inicio,
        fin=fin,
        grados=grados,
        secciones=secciones,
        grado_id=grado_id,
        seccion_id=seccion_id
    )


# ======================================================
# REPORTE PDF
# ======================================================

@app.route("/reporte_pdf")
@login_required
def reporte_pdf():

    from reportlab.lib.pagesizes import letter

    # ========= DATOS FORM
    profesora = request.args.get("profesora", "")
    dni_prof = request.args.get("dni_prof", "")
    curso = request.args.get("curso", "")
    grado_id = request.args.get("grado", type=int)
    seccion_id = request.args.get("seccion", type=int)
    fecha_base = request.args.get("fecha")
    tipo = request.args.get("tipo", "dia")

    # ========= FECHA
    if fecha_base:
        base = datetime.strptime(fecha_base, "%Y-%m-%d").date()
    else:
        base = date.today()

    inicio = fin = base

    if tipo == "semana":
        inicio = base - timedelta(days=base.weekday())
        fin = inicio + timedelta(days=6)
    elif tipo == "mes":
        inicio = base.replace(day=1)
    elif tipo == "anio":
        inicio = base.replace(month=1, day=1)

    # ========= FILTRO ALUMNOS
    alumnos_ids = []
    grado_txt = ""
    seccion_txt = ""

    if grado_id:
        grado = Grado.query.get(grado_id)
        grado_txt = grado.nombre

    if seccion_id:
        seccion = Seccion.query.get(seccion_id)
        seccion_txt = seccion.nombre
        alumnos_ids = [a.id for a in seccion.alumnos]

    query = Asistencia.query.filter(Asistencia.fecha.between(inicio, fin))

    if alumnos_ids:
        query = query.filter(Asistencia.alumno_id.in_(alumnos_ids))

    registros = query.all()

    total = len(registros)   # ⭐ CONTADOR

    # ========= PDF
    filename = "reporte_asistencia.pdf"
    filepath = os.path.join("static", filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = []

    # ===== TITULO
    elements.append(Paragraph("REPORTE OFICIAL DE ASISTENCIA", styles["Heading1"]))
    elements.append(Spacer(1, 20))

    info = f"""
    Profesora: {profesora}<br/>
    DNI: {dni_prof}<br/>
    Curso: {curso}<br/>
    Grado: {grado_txt} &nbsp;&nbsp; Sección: {seccion_txt}<br/>
    Periodo: {inicio} al {fin}<br/>
    Total alumnos registrados: <b>{total}</b>
    """

    elements.append(Paragraph(info, styles["Normal"]))
    elements.append(Spacer(1, 25))

    # ===== TABLA
    data = [["Fecha", "Alumno", "DNI", "Estado"]]

    for r in registros:
        data.append([
            str(r.fecha),
            r.alumno.nombre,
            r.alumno.dni,
            r.estado
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER")
    ]))

    elements.append(table)

    elements.append(Spacer(1, 50))

    # ===== FIRMA
    elements.append(Paragraph("Firma: _________________________________", styles["Normal"]))

    doc.build(elements)

    return send_file(filepath, as_attachment=True)




# ======================================================
# SECCIONES
# ======================================================

@app.route("/secciones/<int:grado_id>", methods=["GET", "POST"])
@login_required
def secciones(grado_id):

    grado = Grado.query.get_or_404(grado_id)

    if request.method == "POST":
        db.session.add(Seccion(nombre=request.form["nombre"], grado_id=grado_id))
        db.session.commit()

    return render_template(
        "secciones.html",
        grado=grado,
        secciones=grado.secciones
    )


# ======================================================
# ALUMNOS POR SECCION (UNICO CRUD)
# ======================================================

@app.route("/alumnos/<int:seccion_id>", methods=["GET", "POST"])
@login_required
def alumnos_seccion(seccion_id):

    seccion = Seccion.query.get_or_404(seccion_id)

    if request.method == "POST":

        foto = request.files.get("foto")
        filename = ""

        if foto and foto.filename != "":
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db.session.add(
            Alumno(
                nombre=request.form["nombre"],
                dni=request.form["dni"],
                foto=filename,
                seccion_id=seccion_id
            )
        )

        db.session.commit()

    return render_template(
        "alumnos.html",
        alumnos=seccion.alumnos,
        seccion=seccion
    )


@app.route("/eliminar_alumno/<int:id>")
@login_required
def eliminar_alumno(id):
    db.session.delete(Alumno.query.get(id))
    db.session.commit()
    return redirect(request.referrer)

# ======================================================
# CURSOS / PLANIFICACION
# ======================================================

@app.route("/cursos", methods=["GET", "POST"])
@login_required
def cursos():

    if request.method == "POST":
        db.session.add(Curso(nombre=request.form["nombre"]))
        db.session.commit()

    return render_template(
        "cursos.html",
        cursos=Curso.query.all()
    )


@app.route("/eliminar_curso/<int:id>")
@login_required
def eliminar_curso(id):
    db.session.delete(Curso.query.get(id))
    db.session.commit()
    return redirect("/cursos")


# ======================
# DETALLE CURSO → competencias
# ======================

@app.route("/curso_detalle/<int:id>", methods=["GET", "POST"])
@login_required
def curso_detalle(id):

    curso = Curso.query.get_or_404(id)

    if request.method == "POST":
        db.session.add(
            Competencia(
                nombre=request.form["nombre"],
                curso_id=id
            )
        )
        db.session.commit()

    return render_template(
        "curso_detalle.html",
        curso=curso,
        competencias=Competencia.query.filter_by(curso_id=id).all()
    )


# ======================
# CAPACIDADES
# ======================

@app.route("/add_capacidad/<int:id>", methods=["POST"])
@login_required
def add_capacidad(id):
    db.session.add(
        Capacidad(
            nombre=request.form["nombre"],
            competencia_id=id
        )
    )
    db.session.commit()
    return redirect(request.referrer)


@app.route("/del_capacidad/<int:id>")
@login_required
def del_capacidad(id):
    db.session.delete(Capacidad.query.get(id))
    db.session.commit()
    return redirect(request.referrer)


# ======================
# RESET SISTEMA + BACKUP
# ======================

@app.route("/reset_sistema", methods=["POST"])
@login_required
def reset_sistema():

    password = request.form.get("password")
    user = User.query.filter_by(username="admin").first()

    if not user or user.password != password:
        flash("Contraseña incorrecta", "danger")
        return redirect("/dashboard")

    os.makedirs("backups", exist_ok=True)

    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backups/backup_{fecha}.db"

    db_path = os.path.join(app.instance_path, "database.db")

    if os.path.exists(db_path):
        shutil.copy(db_path, backup_name)

    Asistencia.query.delete()
    Alumno.query.delete()
    Capacidad.query.delete()
    Competencia.query.delete()
    Curso.query.delete()
    Seccion.query.delete()
    Grado.query.delete()

    db.session.commit()

    flash("Sistema reiniciado con backup creado.", "success")
    return redirect("/dashboard")


# ======================
# RESTAURAR
# ======================

@app.route("/restaurar_backup/<filename>", methods=["POST"])
@login_required
def restaurar_backup(filename):

    password = request.form.get("password")
    user = User.query.filter_by(username="admin").first()

    if not user or user.password != password:
        flash("Contraseña incorrecta", "danger")
        return redirect("/dashboard")

    backup_path = os.path.join("backups", filename)
    db_path = os.path.join(app.instance_path, "database.db")

    db.session.close()
    shutil.copy(backup_path, db_path)

    flash("Backup restaurado. Reinicie la app.", "success")
    return redirect("/dashboard")


# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":

    os.makedirs("static/uploads", exist_ok=True)

    with app.app_context():
        db.create_all()

        if not User.query.first():
            db.session.add(User(username="admin", password="admin"))
            db.session.commit()

    app.run(debug=True)
