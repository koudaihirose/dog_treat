from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from datetime import datetime

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

        # 購入履歴を保存するためのテーブルが必要です。テーブルがない場合は作成してください。
        conn.execute('INSERT INTO purchase_history (snack_id, purchase_date, purchase_place, quantity) VALUES (?, ?, ?, ?)',
                    (snack_name, purchase_date, purchase_place, quantity))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    # snacksテーブルからおやつのリストを取得
    snacks = conn.execute('SELECT id, name FROM snacks').fetchall()
    conn.close()
    return render_template('purchase_snack.html', snacks=snacks)

@app.route('/purchase_history')
def purchase_history():
    conn = get_db_connection()
    
    # 購入履歴を取得
    purchase_history = conn.execute('''
        SELECT p.id, s.name, p.purchase_date, p.purchase_place, p.quantity
        FROM purchase_history p
        JOIN snacks s ON p.snack_id = s.id
        ORDER BY p.purchase_date DESC
    ''').fetchall()
    
    conn.close()
    return render_template('purchase_history.html', purchase_history=purchase_history)


@app.route('/give_snack', methods=['GET', 'POST'])
def give_snack():
    conn = get_db_connection()

    # snacksテーブルからおやつのリストを取得
    snacks = conn.execute('SELECT id, name FROM snacks').fetchall()

    if request.method == 'POST':
        snack_id = request.form['snack_id']
        quantity = int(request.form['quantity'])
        give_date = request.form['given_date']

        # おやつを与える処理を実行
        conn.execute('INSERT INTO snack_giving (snack_id, quantity, given_date) VALUES (?, ?, ?)',
                    (snack_id, quantity, give_date))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('give_snack.html', snacks=snacks)

@app.route('/give_history')
def give_snack_history():
    conn = get_db_connection()

    # 消費履歴を取得
    give_snack_history = conn.execute('''
        SELECT g.id, s.name, g.quantity, g.given_date
        FROM snack_giving g
        JOIN snacks s ON g.snack_id = s.id
        ORDER BY g.given_date DESC
    ''').fetchall()

    conn.close()
    return render_template('give_snack_history.html', give_snack_history=give_snack_history)

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


@app.errorhandler(405)
def method_not_allowed(e):
    return "Method not allowed. Please check the URL and method.", 405

if __name__ == '__main__':
    app.run(debug=True)