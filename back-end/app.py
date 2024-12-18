from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import signal, sys
import os
import psycopg2.pool
from json import dumps

app = Flask(__name__, template_folder='../front-end/templates', static_folder='../front-end/static')


# Достаём секреты из файлов
with open(os.environ['DB_USER'], 'r', encoding='utf-8') as f_u: DB_USER = f_u.read()
with open(os.environ['DB_PASS'], 'r', encoding='utf-8') as f_p: DB_PASS = f_p.read()

# DB connection
pool = psycopg2.pool.SimpleConnectionPool(1, 3, host='db', dbname="DB_Lab", user=DB_USER, password=DB_PASS)

def query_db(query, args=(), one=False):
    conn = pool.getconn()
    cur = conn.cursor()

    cur.execute(query, args)
    r = [dict((cur.description[i][0], value) \
        for i, value in enumerate(row)) for row in cur.fetchall()]
    
    pool.putconn(conn)
    return (r[0] if r else None) if one else r

# ------ 
# ROUTES
# ------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sellings', methods=['GET'], defaults={'page': 1, 'records_per_page': 20, 'start_date': None, 'end_date': None})
def list_sellings(page, records_per_page, start_date, end_date):
    # Получаем соединение с БД
    sql_string = f"""
            SELECT p.product_name "Имя продукта", a.affiliate_address "Адрес магазина", g.goods_realised_quantity "Товара реализовано",
            g.goods_realised_price "Стоимость реализованного товара", g.goods_recieved_quantity "Товара получено", g.goods_recieved_cost "Стоимость полученного товара", 
            g.goods_date "Дата"
            FROM goods_movement g
            JOIN product p on p.product_id = g.product_id
            JOIN affiliate a on a.affiliate_id = g.affiliate_id
            LIMIT %s offset %s
        """

    return render_template('table.html', data=query_db(sql_string, (records_per_page, (page-1) * records_per_page)))


@app.route('/assortiment', methods=['GET'], defaults={'page': 1, 'records_per_page': 20, 'start_date': None, 'end_date': None})
def list_assortiment(page, records_per_page, start_date, end_date):
    sql_string = f"""
        SELECT a.affiliate_id "Магазин", p.product_name "Продукт", 
        s.stock_quantity "Количество", s.stock_price "Стоимость", s.stock_delivery "Ежедневная поставка"
        FROM stock s
        JOIN affiliate a on a.affiliate_id = s.affiliate_id
        JOIN product p on p.product_id = s.product_id
        limit 10 offset 1
    """
    return render_template('table.html', data=query_db(sql_string, (records_per_page, (page-1) * records_per_page)))


@app.route('/orders', methods=['GET'], defaults={'page': 1, 'records_per_page': 20, 'start_date': None, 'end_date': None})
def list_orders(page, records_per_page, start_date, end_date):
    sql_string = f"""
        SELECT pa.partner_name "Партнер", product_name "Продукт", o.order_date "Дата",
        o.order_price "Стоимость", o.order_quantity "Количество", o.order_status "Статус"
        FROM "order" o
        JOIN partner pa ON pa.partner_id = o.partner_id
        JOIN product pr ON pr.product_id = o.product_id
        limit 20 offset 0
    """

    return render_template('table.html', data=query_db(sql_string, (records_per_page, (page-1) * records_per_page)))

# Обрабатываем сигнал завершения 
def stop_server(signal=None, frame=None):
    print("Stopping server")
    sys.exit(0)


# ловушка для ручного закрытия контейнера
signal.signal(signal.SIGTERM, stop_server)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
    stop_server()