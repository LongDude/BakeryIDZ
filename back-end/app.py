from flask import Flask, render_template, request, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateField, IntegerField, DecimalField, SelectField
from wtforms.validators import NumberRange
import psycopg2
import signal, sys
import os
import psycopg2.pool
from json import dumps

app = Flask(__name__, template_folder='../front-end/templates', static_folder='../front-end/static')
app.config['SECRET_KEY'] = 'DEBUG_ONLY_KEY'

# Достаём секреты из файлов
with open(os.environ['DB_USER'], 'r', encoding='utf-8') as f_u: DB_USER = f_u.read()
with open(os.environ['DB_PASS'], 'r', encoding='utf-8') as f_p: DB_PASS = f_p.read()

# DB connection
pool = psycopg2.pool.SimpleConnectionPool(1, 3, host='db', dbname="DB_Lab", user=DB_USER, password=DB_PASS)

RECORDS_PER_PAGE = 20

def query_db(query, one=False):
    conn = pool.getconn()
    cur = conn.cursor()

    cur.execute(query)
    r = [dict((cur.description[i][0], value) \
        for i, value in enumerate(row)) for row in cur.fetchall()]
    
    pool.putconn(conn)
    return (r[0] if r else None) if one else r


# -----------------------
# Дъявольские технологии™
# Надо было делать ORM
# -----------------------
def append_filter(query: str, q_mask, q_filter = ()):
    if q_filter is None or len(q_filter) == 0:
        return query
    p = 0
    while p < len(q_filter):
        # Получаем код поля
        try:
            fkey = q_mask[q_filter[p]]
        except KeyError:
            app.logger.debug(q_filter[p], q_mask)

        ftype = q_filter[p+ 1]
        match ftype:
            case 'eq':
                val1 = q_filter[p + 2]
                if not val1.isnumeric():
                    # Для строк экранируем кавычки
                    val1 = f'\'{val1}\'' 
                query += f" WHERE {fkey} = {val1}"
                break
            case 'ls':
                val1 = q_filter[p + 2]
                if not val1.isnumeric():
                    val1 = f'\'{val1}\'' 
                query += f" WHERE {fkey} < {val1}"
                break
            case 'gt':
                val1 = q_filter[p + 2]
                if not val1.isnumeric():
                    val1 = f'\'{val1}\'' 
                query += f" WHERE {fkey} > {val1}"
                break
            case 'bt':
                val1 = q_filter[p + 2]
                val2 = q_filter[p + 3]
                if not val1.isnumeric():
                    val1 = f'\'{val1}\'' 
                if not val2.isnumeric():
                    val2 = f'\'{val2}\'' 
                query += f" WHERE {fkey} BETWEEN {val1} and {val2}"
                p += 1
                break
        p += 3
    return query

def append_sort(query: str, sortby = ()):
    if sortby is None or len(sortby) == 0:
        return query
    query += ' ORDER BY '
    p = 0
    while p < len(sortby):
        if p > 0:
            query += ', '
        query += f'\"{sortby[p]}\" {sortby[p+1]}'
        p += 2
    return query

def append_pagination(query: str, page=1, limit=RECORDS_PER_PAGE):
    return query + f" LIMIT {limit} offset {(page - 1) * limit}"

def complex_table_request(query, query_codes, args,  req_count=False):
    # Filtration
    arg_filter = args.get('filterBy', type=str, default=None)
    if arg_filter is not None:
        arg_filter = list(arg_filter.split(','))
    query = append_filter(query, query_codes, arg_filter)

    if req_count:
        return query_db(f"SELECT COUNT(*) FROM ({query})")

    # Ordering
    arg_order = args.get('orderBy', type=str, default=None)
    if arg_order is not None:
        arg_order = list(arg_order.split(','))
    query = append_sort(query, arg_order)


    # Pagination
    arg_page = args.get('page', type=int, default=1)
    arg_pagelimit = args.get('limit', type=int, default=20)
    query = append_pagination(query, arg_page, arg_pagelimit)

    return query_db(query)

# ------ 
# ROUTES
# ------
@app.route('/')
def index():
    return render_template('index.html')

# Работа с таблицами

# -- Вспомогательные запросы --
@app.route('/affiliates/all', methods=['GET'])
def list_affiliates_all(): return query_db("SELECT affiliate_id, affiliate_address FROM affiliate ORDER BY affiliate_id")

@app.route('/partners/all', methods=['GET'])
def list_partners_all(): return query_db("SELECT partner_id, partner_name FROM partner ORDER BY partner_id")

@app.route('/products/all', methods=['GET'])
def list_products_all(): return query_db("SELECT product_id, product_name FROM product ORDER BY product_id")


# -- Продажи --
SQL_SELLINGS_TABLE = """
            SELECT p.product_name "Имя продукта", a.affiliate_address "Адрес магазина", g.goods_realised_quantity "Товара реализовано",
            g.goods_realised_price "Стоимость реализованного товара", g.goods_recieved_quantity "Товара получено", g.goods_recieved_cost "Стоимость полученного товара", 
            g.goods_date "Дата"
            FROM goods_movement g
            JOIN product p on p.product_id = g.product_id
            JOIN affiliate a on a.affiliate_id = g.affiliate_id
        """

SQL_SELLING_MASKS = {
    "Имя продукта"                  : "p.product_name ",
    "Адрес магазина"                : "a.affiliate_address", 
    "Товара реализовано"            : "g.goods_realised_quantity",
    "Стоимость реализованного товара" : "g.goods_realised_price", 
    "Товара получено"               : "g.goods_recieved_quantity", 
    "Стоимость полученного товара"  : "g.goods_recieved_cost", 
    "Дата"                          : "g.goods_date" 
}

class SellForm(FlaskForm):
    product_name = SelectField(choices=[
        (x['product_id'], x['product_name']) for x in list_products_all()])
    affiliate_address = SelectField(choices=[
        (x['affiliate_id'], x['affiliate_address']) for x in list_affiliates_all()
    ])
    goods_realised = IntegerField(validators=[NumberRange(0)])
    goods_realised_price = DecimalField(validators=[NumberRange(0)])
    goods_recieved = IntegerField(validators=[NumberRange(0)])
    goods_recieved_cost = DecimalField(validators=[NumberRange(0)])
    date = DateField(format="%Y-%m-%d")

@app.route('/sellings', methods=['GET'])
def list_sellings():
    return render_template('table.html', data=complex_table_request(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args), pages=(count_sellings()[0]['count'] + RECORDS_PER_PAGE - 1) // RECORDS_PER_PAGE)

@app.route('/sellings/count', methods=['GET'])
def count_sellings():
    return complex_table_request(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args, True)

@app.route('/sellings', methods=['POST'])
def sellings_create():
    pass

@app.route('/sellings', methods=['PUT'])
def sellings_update():
    pass

@app.route('/sellings', methods=['DEL'])
def sellings_delete():
    pass

# -- Ассортимент --
SQL_ASSORTIMENT_TABLE = """
        SELECT a.affiliate_address "Магазин", p.product_name "Продукт", 
        s.stock_quantity "Количество", s.stock_price "Стоимость", s.stock_delivery "Ежедневная поставка"
        FROM stock s
        JOIN affiliate a on a.affiliate_id = s.affiliate_id
        JOIN product p on p.product_id = s.product_id
    """

SQL_ASSORTIMENT_MASK = {
    "Магазин"               : "a.affiliate_address", 
    "Продукт"               : "p.product_name", 
    "Количество"            : "s.stock_quantity", 
    "Стоимость"             : "s.stock_price", 
    "Ежедневная поставка"   : "s.stock_delivery"
}
@app.route('/assortiment', methods=['GET'])
def list_assortiment():
    return render_template('table.html', data=complex_table_request(SQL_ASSORTIMENT_TABLE, SQL_ASSORTIMENT_MASK, request.args), pages=(count_assortiment()[0]['count'] + RECORDS_PER_PAGE - 1) // RECORDS_PER_PAGE)

@app.route('/assortiment/count', methods=['GET'])
def count_assortiment():
    return complex_table_request(SQL_SELLINGS_TABLE, SQL_ASSORTIMENT_MASK, request.args, True)

# -- Заказы --
SQL_ORDERS_TABLE = """
        SELECT pa.partner_name "Партнер", product_name "Продукт", o.order_date "Дата",
        o.order_price "Стоимость", o.order_quantity "Количество", o.order_status "Статус"
        FROM "order" o
        JOIN partner pa ON pa.partner_id = o.partner_id
        JOIN product pr ON pr.product_id = o.product_id
    """

SQL_ORDERS_MASK = {
    "Партнер"   : "pa.partner_name", 
    "Продукт"   : "product_name", 
    "Дата"      : "o.order_date",
    "Стоимость" : "o.order_price", 
    "Количество": "o.order_quantity", 
    "Статус"    : "o.order_status"
}
@app.route('/orders', methods=['GET'])
def list_orders():
    return render_template('table.html', data=complex_table_request(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args), pages=(count_orders()[0]['count'] + RECORDS_PER_PAGE - 1) // RECORDS_PER_PAGE)

@app.route('/orders/count', methods=['GET'])
def count_orders():
    return complex_table_request(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args, True)


# Обрабатываем сигнал завершения 
def stop_server(signal=None, frame=None):
    print("Stopping server")
    sys.exit(0)


# ловушка для ручного закрытия контейнера
signal.signal(signal.SIGTERM, stop_server)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
    stop_server()