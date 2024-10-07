from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

# データベースに接続するヘルパー関数
def get_db_connection():
    conn = sqlite3.connect('dog_treats.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()

    # おやつの在庫数を計算
    snacks = conn.execute('''
        SELECT s.id, s.name, s.quantity,
               COALESCE(SUM(g.quantity), 0) AS consumed,
               (s.quantity - COALESCE(SUM(g.quantity), 0)) AS stock,
               COALESCE(GROUP_CONCAT(a.name, ', '), 'なし') AS allergies
        FROM snacks s
        LEFT JOIN snack_giving g ON s.id = g.snack_id
        LEFT JOIN snack_allergies sa ON s.id = sa.snack_id
        LEFT JOIN allergies a ON sa.allergy_id = a.id
        GROUP BY s.id
    ''').fetchall()

    conn.close()
    return render_template('index.html', snacks=snacks)



@app.route('/add_snack', methods=['GET', 'POST'])
def add_snack():
    conn = get_db_connection()

    if request.method == 'POST':
        # snack_nameが存在するか確認
        snack_name = request.form.get('snack_name')
        if not snack_name:
            return "Snack name is required", 400  # 400エラーを返す

        quantity = request.form['quantity']
        allergy_ids = request.form.getlist('allergy_ids')

        # snacksテーブルに新しいおやつを追加
        conn.execute('INSERT INTO snacks (name, quantity) VALUES (?, ?)',
                    (snack_name, quantity))
        conn.commit()

        snack_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        if allergy_ids:
            for allergy_id in allergy_ids:
                conn.execute('INSERT INTO snack_allergies (snack_id, allergy_id) VALUES (?, ?)',
                            (snack_id, allergy_id))
            conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    # GETリクエストの場合はアレルギー情報を取得
    allergies = conn.execute('SELECT id, name FROM allergies').fetchall()
    conn.close()
    return render_template('add_snack.html', allergies=allergies)

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

@app.errorhandler(405)
def method_not_allowed(e):
    return "Method not allowed. Please check the URL and method.", 405

if __name__ == '__main__':
    app.run(debug=True)