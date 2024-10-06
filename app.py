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
    # snacks テーブルと snack_giving テーブルを結合して在庫数を計算
    snacks = conn.execute('''
        SELECT 
            snacks.id, 
            snacks.name, 
            snacks.description, 
            snacks.purchase_date, 
            snacks.quantity AS purchased_quantity,
            IFNULL(SUM(snack_giving.quantity), 0) AS given_quantity, 
            allergies.name AS allergy_name
        FROM snacks
        LEFT JOIN snack_giving ON snacks.id = snack_giving.snack_id
        LEFT JOIN allergies ON snacks.allergy_id = allergies.id
        GROUP BY snacks.id
    ''').fetchall()
    
    conn.close()
    return render_template('index.html', snacks=snacks)

@app.route('/add_snack', methods=['GET', 'POST'])
def add_snack():
    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        purchase_date = request.form['purchase_date']
        quantity = request.form['quantity']
        allergy_id = request.form['allergy_id']
        
        conn.execute('''
            INSERT INTO snacks (name, description, purchase_date, quantity, allergy_id) 
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, purchase_date, quantity, allergy_id))
        
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    # アレルギー一覧を取得
    allergies = conn.execute('SELECT * FROM allergies').fetchall()
    conn.close()

    return render_template('add_snack.html', allergies=allergies)

@app.route('/give_snack/<int:id>', methods=['GET', 'POST'])
def give_snack(id):
    if request.method == 'POST':
        given_date = request.form['given_date']
        quantity = request.form['quantity']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO snack_giving (snack_id, given_date, quantity) VALUES (?, ?, ?)',
                    (id, given_date, quantity))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    return render_template('give_snack.html', snack_id=id)

def insert_allergies():
    conn = sqlite3.connect('dog_treats.db')
    cur = conn.cursor()

    # アレルギー情報のサンプルを挿入
    allergies = [('牛乳',), ('卵',), ('小麦',), ('大豆',)]
    cur.executemany('INSERT INTO allergies (name) VALUES (?)', allergies)
    
    conn.commit()
    conn.close()
if __name__ == '__main__':
    app.run(debug=True)