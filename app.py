from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename



# アップロードされたファイルの保存先
UPLOAD_FOLDER = 'static/photos'  # staticフォルダの中にphotosフォルダを作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# データベースに接続するヘルパー関数
def get_db_connection():
    conn = sqlite3.connect('dog_treats.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()

    snacks = conn.execute('''
        SELECT s.id, s.name, 
                COALESCE(GROUP_CONCAT(a.name, ', '), 'なし') AS allergies,
                COALESCE(SUM(DISTINCT ph.quantity), 0) AS total_purchased,
                COALESCE(SUM(DISTINCT sg.quantity), 0) AS total_given,
                COALESCE(SUM(DISTINCT ph.quantity), 0, 0) - COALESCE(SUM(DISTINCT sg.quantity), 0) AS stock,
                REPLACE(REPLACE(COALESCE(GROUP_CONCAT(sp.photo_path),'' ), '\\', '/'), 'static/', '') AS photos
        FROM snacks s
        LEFT JOIN snack_allergies sa ON s.id = sa.snack_id
        LEFT JOIN allergies a ON sa.allergy_id = a.id
        LEFT JOIN purchase_history ph ON s.id = ph.snack_id
        LEFT JOIN snack_giving sg ON s.id = sg.snack_id
        LEFT JOIN snack_photos sp ON s.id = sp.snack_id
        GROUP BY s.id
    ''').fetchall()

    conn.close()
    return render_template('index.html', snacks=snacks)




@app.route('/add_snack', methods=['GET', 'POST'])
def add_snack():
    conn = get_db_connection()
    if request.method == 'POST':
        snack_name = request.form['snack_name']
        allergy_ids = request.form.getlist('allergy_ids')

        conn = get_db_connection()

        # snacksテーブルに新しいおやつを追加
        conn.execute('INSERT INTO snacks (name) VALUES (?)', (snack_name,))
        conn.commit()

        # 最後に追加されたおやつのIDを取得
        snack_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        # アップロードされたファイルを保存
        files = request.files.getlist('photos')  # フォームからのファイル取得
        for file in files:
            if file and file.filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
                # snack_photosテーブルに写真のパスを追加
                conn.execute('INSERT INTO snack_photos (snack_id, photo_path) VALUES (?, ?)',
                            (snack_id, file_path))
        conn.commit()

        # アレルギー情報を関連付け
        if allergy_ids:
            for allergy_id in allergy_ids:
                conn.execute('INSERT INTO snack_allergies (snack_id, allergy_id) VALUES (?, ?)',
                            (snack_id, allergy_id))
                conn.commit()

    # GETリクエストの場合はアレルギー情報を取得
    allergies = conn.execute('SELECT id, name FROM allergies').fetchall()

    conn.close()
    return render_template('add_snack.html', allergies=allergies)

@app.route('/purchase_snack', methods=['GET', 'POST'])
def purchase_snack():
    conn = get_db_connection()

    if request.method == 'POST':
        snack_name = request.form['snack_name']
        purchase_date = request.form['purchase_date']
        purchase_place = request.form['purchase_place']
        quantity = request.form['quantity']

        # 'T'をスペースに置き換える
        formatted_purchase_date = purchase_date.replace('T', ' ')

        # 購入履歴を保存するためのテーブルが必要です。テーブルがない場合は作成してください。
        conn.execute('INSERT INTO purchase_history (snack_id, purchase_date, purchase_place, quantity) VALUES (?, ?, ?, ?)',
                    (snack_name, formatted_purchase_date, purchase_place, quantity))
        conn.commit()

    # snacksテーブルからおやつのリストを取得
    snacks = conn.execute('SELECT id, name FROM snacks').fetchall()

    # 購入履歴を取得
    purchase_history = conn.execute('''
        SELECT p.id, s.name, p.purchase_date, p.purchase_place, p.quantity
        FROM purchase_history p
        JOIN snacks s ON p.snack_id = s.id
        ORDER BY p.purchase_date DESC
    ''').fetchall()

    conn.close()
    return render_template('purchase_snack.html', snacks=snacks, purchase_history=purchase_history)

@app.route('/give_snack', methods=['GET', 'POST'])
def give_snack():
    conn = get_db_connection()

    if request.method == 'POST':
        snack_id = request.form['snack_id']
        quantity = int(request.form['quantity'])
        give_date = request.form['given_date']

        # 'T'をスペースに置き換える
        formatted_give_date = give_date.replace('T', ' ')

        # おやつを与える処理を実行
        conn.execute('INSERT INTO snack_giving (snack_id, quantity, given_date) VALUES (?, ?, ?)',
                    (snack_id, quantity, formatted_give_date))
        conn.commit()

    # snacksテーブルからおやつのリストを取得
    snacks = conn.execute('SELECT id, name FROM snacks').fetchall()

    # 消費履歴を取得
    give_snack_history = conn.execute('''
        SELECT g.id, s.name, g.quantity, g.given_date
        FROM snack_giving g
        JOIN snacks s ON g.snack_id = s.id
        ORDER BY g.given_date DESC
    ''').fetchall()
    
    conn.close()
    return render_template('give_snack.html', snacks=snacks, give_snack_history=give_snack_history)


@app.route('/allergies', methods=['GET', 'POST'])
def allergies():
    conn = get_db_connection()

    # POSTリクエストの場合はフォームのデータを受け取ってアレルギーテーブルに追加
    if request.method == 'POST':
        allergy_name = request.form['allergy_name']
        if allergy_name:  # 空のデータが送信されないようにチェック
            conn.execute('INSERT INTO allergies (name) VALUES (?)', (allergy_name,))
            conn.commit()

    # allergiesテーブルから全てのアレルギー情報を取得
    allergies = conn.execute('SELECT id, name FROM allergies').fetchall()

    conn.close()
    return render_template('allergies.html', allergies=allergies)

@app.route('/stock')
def stock():
    conn = get_db_connection()

    snacks = conn.execute('''
        SELECT s.id, s.name, 
                COALESCE(GROUP_CONCAT(a.name, ', '), 'なし') AS allergies,
                COALESCE(SUM(DISTINCT ph.quantity), 0) AS total_purchased,
                COALESCE(SUM(DISTINCT sg.quantity), 0) AS total_given,
                COALESCE(SUM(DISTINCT ph.quantity), 0, 0) - COALESCE(SUM(DISTINCT sg.quantity), 0) AS stock,
                REPLACE(REPLACE(COALESCE(GROUP_CONCAT(sp.photo_path),'' ), '\\', '/'), 'static/', '') AS photos
        FROM snacks s
        LEFT JOIN snack_allergies sa ON s.id = sa.snack_id
        LEFT JOIN allergies a ON sa.allergy_id = a.id
        LEFT JOIN purchase_history ph ON s.id = ph.snack_id
        LEFT JOIN snack_giving sg ON s.id = sg.snack_id
        LEFT JOIN snack_photos sp ON s.id = sp.snack_id
        GROUP BY s.id
    ''').fetchall()

    conn.close()
    return render_template('stock.html', snacks=snacks)

# 異常記録を追加するルート
@app.route('/add_incident_record', methods=['GET', 'POST'])
def add_incident_record():
    if request.method == 'POST':
        incident_time = request.form['incident_time']
        note = request.form['note']
        photos = request.files.getlist('photos')  # 複数ファイルの取得

        # 'T'をスペースに置き換える
        formatted_incident_time = incident_time.replace('T', ' ')

        conn = get_db_connection()

        # incident_recordsテーブルに記録を追加
        conn.execute('INSERT INTO incident_records (incident_time, note) VALUES (?, ?)',
                    (formatted_incident_time, note))
        conn.commit()

        # 追加した記録のIDを取得
        incident_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        # 写真を保存し、incident_photosテーブルに関連付ける
        for photo in photos:
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                photo_path = os.path.join('static/incident_photos', filename)
                photo.save(photo_path)

                conn.execute('INSERT INTO incident_photos (incident_id, photo_path) VALUES (?, ?)',
                            (incident_id, photo_path))

        conn.commit()
        conn.close()
        return redirect(url_for('incident_records'))

    return render_template('incident_records.html')

@app.route('/incident_records')
def incident_records():
    conn = get_db_connection()

    # incident_recordsとincident_photosのデータを結合して取得
    incident_records = conn.execute('''
        SELECT ir.id, ir.incident_time, ir.note, 
            REPLACE(REPLACE(GROUP_CONCAT(ip.photo_path, ', '), '\\', '/'), 'static/', '') AS photos
        FROM incident_records ir
        LEFT JOIN incident_photos ip ON ir.id = ip.incident_id
        GROUP BY ir.id
    ''').fetchall()

    conn.close()
    return render_template('incident_records.html', incident_records=incident_records)

if __name__ == '__main__':
    app.run(debug=True)