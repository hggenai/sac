import os
from functools import wraps
from datetime import datetime, date
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session)
from models import db, University, Department, Professor, SalesInfo, CustomField, CustomFieldValue, SALES_STATUSES
import scraper

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# DB設定
database_url = os.environ.get('DATABASE_URL', 'sqlite:///sales.db')
# Supabase / Render が postgres:// を返す場合の対応
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# ─────────────────────────────────────────────
# 認証
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', '')
        if not admin_pass:
            error = 'ADMIN_PASSWORD が設定されていません（環境変数を確認してください）'
        elif username == admin_user and password == admin_pass:
            session['logged_in'] = True
            session.permanent = True
            next_url = request.args.get('next') or url_for('dashboard')
            return redirect(next_url)
        else:
            error = 'ユーザー名またはパスワードが違います'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    flash('ログアウトしました', 'info')
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def ensure_sales_info(professor):
    if professor.sales_info is None:
        si = SalesInfo(professor_id=professor.id, status='未接触', tags=[])
        db.session.add(si)
        db.session.commit()
    return professor.sales_info


# ─────────────────────────────────────────────
# ダッシュボード
# ─────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    universities = University.query.all()
    total_professors = Professor.query.count()

    status_counts = {}
    for status in SALES_STATUSES:
        count = SalesInfo.query.filter_by(status=status).count()
        status_counts[status] = count
    no_info_count = Professor.query.filter(
        ~Professor.id.in_(db.session.query(SalesInfo.professor_id))
    ).count()
    if no_info_count > 0:
        status_counts['未接触'] = status_counts.get('未接触', 0) + no_info_count

    univ_counts = []
    for u in universities:
        univ_counts.append({'name': u.name, 'count': len(u.professors)})

    today = date.today()
    upcoming = SalesInfo.query.filter(
        SalesInfo.next_contact >= today
    ).order_by(SalesInfo.next_contact).limit(10).all()

    return render_template(
        'dashboard.html',
        universities=universities,
        total_professors=total_professors,
        status_counts=status_counts,
        univ_counts=univ_counts,
        upcoming=upcoming,
        statuses=SALES_STATUSES,
    )


# ─────────────────────────────────────────────
# 大学管理
# ─────────────────────────────────────────────

@app.route('/universities')
@login_required
def universities():
    univs = University.query.order_by(University.name).all()
    return render_template('universities.html', universities=univs)


@app.route('/universities/new', methods=['GET', 'POST'])
@login_required
def new_university():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('大学名は必須です', 'danger')
            return redirect(url_for('new_university'))
        u = University(
            name=name,
            url=request.form.get('url', '').strip(),
            note=request.form.get('note', '').strip(),
        )
        db.session.add(u)
        db.session.commit()
        flash(f'「{u.name}」を登録しました', 'success')
        return redirect(url_for('universities'))
    return render_template('university_form.html', university=None)


@app.route('/universities/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
def edit_university(uid):
    u = University.query.get_or_404(uid)
    if request.method == 'POST':
        u.name = request.form.get('name', '').strip()
        u.url = request.form.get('url', '').strip()
        u.note = request.form.get('note', '').strip()
        db.session.commit()
        flash('大学情報を更新しました', 'success')
        return redirect(url_for('universities'))
    return render_template('university_form.html', university=u)


@app.route('/universities/<int:uid>/delete', methods=['POST'])
@login_required
def delete_university(uid):
    u = University.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    flash('大学を削除しました', 'success')
    return redirect(url_for('universities'))


@app.route('/universities/<int:uid>/scrape', methods=['POST'])
@login_required
def scrape_university(uid):
    u = University.query.get_or_404(uid)
    if not u.url:
        flash('大学のURLが登録されていません', 'danger')
        return redirect(url_for('universities'))

    professors, error = scraper.scrape_university(u.url)
    if error:
        flash(f'スクレイピングエラー: {error}', 'danger')
        return redirect(url_for('universities'))

    added = 0
    for p_data in professors:
        existing = Professor.query.filter_by(
            university_id=u.id, name=p_data['name']
        ).first()
        if not existing:
            prof = Professor(
                university_id=u.id,
                name=p_data['name'],
                title=p_data.get('title', ''),
                email=p_data.get('email', ''),
                phone=p_data.get('phone', ''),
                photo_url=p_data.get('photo_url', ''),
                specialty=p_data.get('specialty', ''),
                source_url=p_data.get('source_url', ''),
            )
            db.session.add(prof)
            added += 1

    db.session.commit()
    flash(f'スクレイピング完了: {added}件追加（重複スキップ含む）', 'success')
    return redirect(url_for('universities'))


# ─────────────────────────────────────────────
# 学科管理
# ─────────────────────────────────────────────

@app.route('/universities/<int:uid>/departments/new', methods=['GET', 'POST'])
@login_required
def new_department(uid):
    u = University.query.get_or_404(uid)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('学科名は必須です', 'danger')
            return redirect(url_for('new_department', uid=uid))
        dept = Department(
            university_id=uid,
            name=name,
            url=request.form.get('url', '').strip(),
        )
        db.session.add(dept)
        db.session.commit()
        flash(f'学科「{dept.name}」を追加しました', 'success')
        return redirect(url_for('universities'))
    return render_template('department_form.html', university=u, department=None)


# ─────────────────────────────────────────────
# 教授一覧
# ─────────────────────────────────────────────

@app.route('/professors')
@login_required
def professors():
    query = Professor.query

    univ_id = request.args.get('university_id', type=int)
    dept_id = request.args.get('dept_id', type=int)
    status = request.args.get('status', '')
    tag = request.args.get('tag', '')
    search = request.args.get('q', '').strip()

    if univ_id:
        query = query.filter_by(university_id=univ_id)
    if dept_id:
        query = query.filter_by(dept_id=dept_id)
    if search:
        query = query.filter(
            db.or_(
                Professor.name.contains(search),
                Professor.specialty.contains(search),
                Professor.email.contains(search),
            )
        )

    profs = query.order_by(Professor.university_id, Professor.name).all()

    if status:
        profs = [p for p in profs if p.sales_info and p.sales_info.status == status
                 or (not p.sales_info and status == '未接触')]
    if tag:
        profs = [p for p in profs if p.sales_info and tag in p.sales_info.tags]

    universities = University.query.order_by(University.name).all()
    departments = Department.query.all()

    all_tags = set()
    for si in SalesInfo.query.all():
        all_tags.update(si.tags)

    return render_template(
        'professors.html',
        professors=profs,
        universities=universities,
        departments=departments,
        statuses=SALES_STATUSES,
        all_tags=sorted(all_tags),
        current_filters={
            'university_id': univ_id,
            'dept_id': dept_id,
            'status': status,
            'tag': tag,
            'q': search,
        },
    )


@app.route('/professors/new', methods=['GET', 'POST'])
@login_required
def new_professor():
    if request.method == 'POST':
        university_id = request.form.get('university_id', type=int)
        name = request.form.get('name', '').strip()
        if not university_id or not name:
            flash('大学と氏名は必須です', 'danger')
            universities = University.query.all()
            return render_template('professor_form.html', professor=None, universities=universities,
                                   departments=Department.query.all())
        prof = Professor(
            university_id=university_id,
            dept_id=request.form.get('dept_id', type=int) or None,
            name=name,
            title=request.form.get('title', '').strip(),
            email=request.form.get('email', '').strip(),
            phone=request.form.get('phone', '').strip(),
            photo_url=request.form.get('photo_url', '').strip(),
            specialty=request.form.get('specialty', '').strip(),
            source_url=request.form.get('source_url', '').strip(),
        )
        db.session.add(prof)
        db.session.commit()
        flash(f'「{prof.name}」を登録しました', 'success')
        return redirect(url_for('professor_detail', pid=prof.id))
    universities = University.query.order_by(University.name).all()
    departments = Department.query.all()
    return render_template('professor_form.html', professor=None, universities=universities, departments=departments)


# ─────────────────────────────────────────────
# 教授詳細
# ─────────────────────────────────────────────

@app.route('/professors/<int:pid>')
@login_required
def professor_detail(pid):
    prof = Professor.query.get_or_404(pid)
    ensure_sales_info(prof)
    db.session.refresh(prof)

    custom_fields = CustomField.query.order_by(CustomField.order, CustomField.id).all()
    cf_values = {cfv.custom_field_id: cfv.value for cfv in prof.custom_field_values}

    all_tags = set()
    for si in SalesInfo.query.all():
        all_tags.update(si.tags)

    return render_template(
        'professor_detail.html',
        prof=prof,
        statuses=SALES_STATUSES,
        custom_fields=custom_fields,
        cf_values=cf_values,
        all_tags=sorted(all_tags),
    )


@app.route('/professors/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def edit_professor(pid):
    prof = Professor.query.get_or_404(pid)
    if request.method == 'POST':
        prof.university_id = request.form.get('university_id', type=int)
        prof.dept_id = request.form.get('dept_id', type=int) or None
        prof.name = request.form.get('name', '').strip()
        prof.title = request.form.get('title', '').strip()
        prof.email = request.form.get('email', '').strip()
        prof.phone = request.form.get('phone', '').strip()
        prof.photo_url = request.form.get('photo_url', '').strip()
        prof.specialty = request.form.get('specialty', '').strip()
        prof.source_url = request.form.get('source_url', '').strip()
        db.session.commit()
        flash('教授情報を更新しました', 'success')
        return redirect(url_for('professor_detail', pid=pid))
    universities = University.query.order_by(University.name).all()
    departments = Department.query.all()
    return render_template('professor_form.html', professor=prof, universities=universities, departments=departments)


@app.route('/professors/<int:pid>/delete', methods=['POST'])
@login_required
def delete_professor(pid):
    prof = Professor.query.get_or_404(pid)
    db.session.delete(prof)
    db.session.commit()
    flash('教授を削除しました', 'success')
    return redirect(url_for('professors'))


@app.route('/professors/<int:pid>/sales', methods=['POST'])
@login_required
def update_sales(pid):
    prof = Professor.query.get_or_404(pid)
    si = ensure_sales_info(prof)

    si.status = request.form.get('status', si.status)
    si.last_contact = parse_date(request.form.get('last_contact'))
    si.next_contact = parse_date(request.form.get('next_contact'))
    si.memo = request.form.get('memo', '').strip()

    tags_raw = request.form.get('tags', '')
    si.tags = [t.strip() for t in tags_raw.split(',') if t.strip()]

    db.session.commit()
    flash('営業情報を更新しました', 'success')
    return redirect(url_for('professor_detail', pid=pid))


@app.route('/professors/<int:pid>/custom_fields', methods=['POST'])
@login_required
def update_custom_fields(pid):
    prof = Professor.query.get_or_404(pid)
    custom_fields = CustomField.query.all()

    for cf in custom_fields:
        value = request.form.get(f'cf_{cf.id}', '').strip()
        existing = CustomFieldValue.query.filter_by(
            professor_id=pid, custom_field_id=cf.id
        ).first()
        if existing:
            existing.value = value
        else:
            cfv = CustomFieldValue(professor_id=pid, custom_field_id=cf.id, value=value)
            db.session.add(cfv)

    db.session.commit()
    flash('カスタムフィールドを更新しました', 'success')
    return redirect(url_for('professor_detail', pid=pid))


# ─────────────────────────────────────────────
# カスタムフィールド管理
# ─────────────────────────────────────────────

@app.route('/custom_fields')
@login_required
def custom_fields():
    fields = CustomField.query.order_by(CustomField.order, CustomField.id).all()
    return render_template('custom_fields.html', fields=fields)


@app.route('/custom_fields/new', methods=['POST'])
@login_required
def new_custom_field():
    name = request.form.get('name', '').strip()
    if not name:
        flash('フィールド名は必須です', 'danger')
        return redirect(url_for('custom_fields'))

    field_type = request.form.get('field_type', 'text')
    options_raw = request.form.get('options', '')
    options = [o.strip() for o in options_raw.split(',') if o.strip()]

    max_order = db.session.query(db.func.max(CustomField.order)).scalar() or 0
    cf = CustomField(name=name, field_type=field_type, order=max_order + 1)
    cf.options = options
    db.session.add(cf)
    db.session.commit()
    flash(f'フィールド「{name}」を追加しました', 'success')
    return redirect(url_for('custom_fields'))


@app.route('/custom_fields/<int:cfid>/edit', methods=['POST'])
@login_required
def edit_custom_field(cfid):
    cf = CustomField.query.get_or_404(cfid)
    cf.name = request.form.get('name', cf.name).strip()
    cf.field_type = request.form.get('field_type', cf.field_type)
    options_raw = request.form.get('options', '')
    cf.options = [o.strip() for o in options_raw.split(',') if o.strip()]
    db.session.commit()
    flash('フィールドを更新しました', 'success')
    return redirect(url_for('custom_fields'))


@app.route('/custom_fields/<int:cfid>/delete', methods=['POST'])
@login_required
def delete_custom_field(cfid):
    cf = CustomField.query.get_or_404(cfid)
    db.session.delete(cf)
    db.session.commit()
    flash('フィールドを削除しました', 'success')
    return redirect(url_for('custom_fields'))


@app.route('/custom_fields/reorder', methods=['POST'])
@login_required
def reorder_custom_fields():
    order_data = request.json
    for item in order_data:
        cf = CustomField.query.get(item['id'])
        if cf:
            cf.order = item['order']
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────
# 印刷ビュー
# ─────────────────────────────────────────────

@app.route('/print')
@login_required
def print_view():
    univ_id = request.args.get('university_id', type=int)
    status = request.args.get('status', '')

    query = Professor.query
    if univ_id:
        query = query.filter_by(university_id=univ_id)

    profs = query.order_by(Professor.university_id, Professor.name).all()
    if status:
        profs = [p for p in profs if p.sales_info and p.sales_info.status == status
                 or (not p.sales_info and status == '未接触')]

    custom_fields = CustomField.query.order_by(CustomField.order, CustomField.id).all()
    universities = University.query.order_by(University.name).all()

    return render_template(
        'print.html',
        professors=profs,
        custom_fields=custom_fields,
        universities=universities,
        statuses=SALES_STATUSES,
        current_filters={'university_id': univ_id, 'status': status},
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
