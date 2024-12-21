from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateField, IntegerField, DecimalField, SelectField
from wtforms.validators import NumberRange, DataRequired
import psycopg2
import signal, sys
import os
import psycopg2.pool
from json import dumps
from io import StringIO
import csv
import pdfkit 

app = Flask(__name__, template_folder='../front-end/templates', static_folder='../front-end/static')
app.config['SECRET_KEY'] = 'DEBUG_ONLY_KEY'
app.config['WTF_CSRF_ENABLED'] = False

# Достаём секреты из файлов
with open(os.environ['DB_USER'], 'r', encoding='utf-8') as f_u: DB_USER = f_u.read()
with open(os.environ['DB_PASS'], 'r', encoding='utf-8') as f_p: DB_PASS = f_p.read()

# DB connection
pool = psycopg2.pool.SimpleConnectionPool(1, 3, host='db', dbname="DB_Lab", user=DB_USER, password=DB_PASS)

RECORDS_PER_PAGE = 20

def query_db(query, args=(), one=False):
    try:
        conn = pool.getconn()
        cur = conn.cursor()

        cur.execute(query, args)
        r = [dict((cur.description[i][0], value) \
            for i, value in enumerate(row)) for row in cur.fetchall()]
        conn.commit()
    except Exception as e:
        app.logger.debug(query)
        app.logger.debug(args)
        app.logger.debug(e)
    finally:
        pool.putconn(conn)
    return (r[0] if r else None) if one else r


# -----------------------
# Дъявольские технологии™
# Надо было делать ORM
# -----------------------
def generate_csv(query, query_mask, args):
    data_query = apply_args(query, query_mask, args, False)
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        file = StringIO()

        app.logger.debug(data_query)
        cur.copy_expert("COPY ({0}) TO STDOUT WITH CSV HEADER".format(data_query), file)
        file.seek(0)
        data = file.read()
        app.logger.debug(data)
    except Exception as e:
        app.logger.debug(data_query)
        app.logger.debug(e)
    finally:
        file.close()
        pool.putconn(conn)
    return data


def append_filter(query: str, q_mask, q_filter = ()):
    if q_filter is None or len(q_filter) < 2:
        return query
    app.logger.debug(q_filter)
    p = 0
    query += " WHERE "
    while p < len(q_filter):
        # Получаем код поля
        fkey = ''
        try:
            fkey = q_mask[q_filter[p]]
        except KeyError:
            app.logger.debug(q_filter[p], q_mask)

        val1 = q_filter[p + 1]
        if not val1.isnumeric():
            # Для строк экранируем кавычки
            val1 = f'\'{val1}\'' 
        query += f" {fkey} = {val1}"
        p += 2

        if p < len(q_filter):
            query += " AND "

    return query

def append_sort(query: str, sortby = ()):
    if sortby is None or len(sortby) < 2:
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

def complex_table_request(query, query_codes, args, req_count=False, paginate=True):
    query = apply_args(query, query_codes, args, (not req_count) and paginate)

    if req_count:
        return query_db(f"SELECT COUNT(*) FROM ({query})")
    
    return query_db(query)

def apply_args(query, query_codes, args, paginate=True):
    # Filtration
    arg_filter = args.get('filterBy', type=str, default=None)
    if arg_filter is not None:
        arg_filter = list(arg_filter.split(','))
    query = append_filter(query, query_codes, arg_filter)


    # Ordering
    arg_order = args.get('orderBy', type=str, default=None)
    if arg_order is not None:
        arg_order = list(arg_order.split(','))
    query = append_sort(query, arg_order)

    # Pagination
    if paginate:
        arg_page = args.get('page', type=int, default=1)
        arg_pagelimit = args.get('limit', type=int, default=RECORDS_PER_PAGE)
        query = append_pagination(query, arg_page, arg_pagelimit)
    return query


# ------ 
# ROUTES
# ------
@app.route('/')
def index():
    return render_template('index.html')

# -- Вспомогательные запросы --
# Список известных филиалов
@app.route('/affiliates/all', methods=['GET'])
def list_affiliates_all(): return query_db("SELECT affiliate_id, affiliate_address FROM affiliate ORDER BY affiliate_id")

# Список партнеров
@app.route('/partners/all', methods=['GET'])
def list_partners_all(): return query_db("SELECT partner_id, partner_name FROM partner ORDER BY partner_id")

# Список продуктов
@app.route('/products/all', methods=['GET'])
def list_products_all(): return query_db("SELECT product_id, product_name FROM product ORDER BY product_id")


# -- Продажи --
# Запрос по таблице продаж с дешифровкой ID продукта/филиала
SQL_SELLINGS_TABLE = """
            SELECT p.product_name "Имя продукта", a.affiliate_address "Адрес магазина", g.goods_realised_quantity "Товара реализовано",
            g.goods_realised_price "Стоимость реализ. товара", g.goods_recieved_quantity "Товара получено", g.goods_recieved_cost "Стоимость получ. товара", 
            g.goods_date "Дата", g.product_id "product_id", g.affiliate_id "affiliate_id"
            FROM goods_movement g
            JOIN product p on p.product_id = g.product_id
            JOIN affiliate a on a.affiliate_id = g.affiliate_id
        """
# Маска для конверсии имени столбца (приходит с формы) в истинное имя (code name)
SQL_SELLING_MASKS = {
    "product_id"          : "p.product_id ",
    "affiliate_id"        : "a.affiliate_id", 
    "goods_realised"      : "g.goods_realised_quantity",
    "goods_realised_price": "g.goods_realised_price", 
    "goods_recieved"      : "g.goods_recieved_quantity", 
    "goods_recieved_cost" : "g.goods_recieved_cost", 
    "date"                : "g.goods_date" 
}

class SellForm(FlaskForm):
    ''' Форма заполнения информации о продаже. Генерирует необходимые input с валидацией '''
    product_id = SelectField(choices=[
        (x['product_id'], x['product_name']) for x in list_products_all()])
    affiliate_id = SelectField(choices=[
        (x['affiliate_id'], x['affiliate_address']) for x in list_affiliates_all()])
    goods_realised = IntegerField(default=0, validators=[NumberRange(0)])
    goods_realised_price = DecimalField(default=0, validators=[NumberRange(0)])
    goods_recieved = IntegerField(default=0,validators=[NumberRange(0)])
    goods_recieved_cost = DecimalField(default=0,validators=[NumberRange(0)])
    date = DateField(format="%Y-%m-%d", validators=[DataRequired()])
    submitForm = SubmitField('Сохранить')


@app.route('/sellings', methods=['GET'])
def list_sellings():
    queryData = complex_table_request(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args)
    # Разбиваем полученную таблицу (queryData) на записи (tableData) и составной PK (idData)
    tableData = []
    idData = []
    for row in queryData:
        product_id = row.pop('product_id')
        affiliate_id = row.pop('affiliate_id')
        date_id = row['Дата']
        tableData.append(row)
        idData.append({
            "product_id": product_id, 
            "affiliate_id": affiliate_id, 
            "date": date_id
        })
    arg_pagelimit = request.args.get('limit', type=int, default=RECORDS_PER_PAGE)
    app.logger.debug('QUERIED DATA')
    # tableData идёт в шаблон как элементы таблицы, idData размещается в атрибуте каждой строки
    return render_template('table.html', data=tableData, idData=idData, pages=(count_sellings()[0]['count'] + arg_pagelimit - 1) // arg_pagelimit)


@app.route('/sellings/count', methods=['GET'])
def count_sellings():
    ''' Подсчитываем количество записей по запросу с фильтрами '''
    return complex_table_request(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args, True)

@app.route('/sellings/add-form', methods=['GET', 'POST'])
def sellings_create_form():
    form = SellForm()
    if request.method == 'POST':
        if form.validate():
            query = """
                INSERT INTO public.goods_movement
                (
                product_id, affiliate_id, 
                goods_realised_quantity, goods_realised_price, 
                goods_recieved_quantity, goods_recieved_cost, 
                goods_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *; 
            """
            q_args = (
                form.product_id.data,
                form.affiliate_id.data,
                form.goods_realised.data,
                form.goods_realised_price.data,
                form.goods_recieved.data,
                form.goods_recieved_cost.data,
                form.date.data
            )

            return jsonify(query_db(query, q_args, True))
        else:
            return jsonify(form.errors), 400
    return render_template('sellings_modal.html', form=form)

@app.route('/sellings/functions', methods=['GET'])
def sellings_input_forms():
    form = SellForm(meta={'csrf': False})
    return render_template('sellings_func.html', form=form)

@app.route('/sellings/edit-form', methods=['PUT'])
def sellings_update_form():
    form = SellForm(meta={'csrf': False})
    if form.validate():
        query = """
        UPDATE public.goods_movement
        SET product_id=%s, affiliate_id=%s, goods_realised_quantity=%s, goods_realised_price=%s, goods_recieved_quantity=%s, goods_recieved_cost=%s, goods_date=%s
        WHERE product_id=%s and affiliate_id=%s and goods_date=%s
        RETURNING *
        """
        
        q_args = (
            form.product_id.data,
            form.affiliate_id.data,
            form.goods_realised.data,
            form.goods_realised_price.data,
            form.goods_recieved.data,
            form.goods_recieved_cost.data,
            form.date.data,
            request.args.get('product_id'),
            request.args.get('affiliate_id'),
            request.args.get('date')
        )

        return jsonify(query_db(query, q_args, True))
    else:
        return jsonify(form.errors), 400

@app.route('/sellings/del-form', methods=['DELETE'])
def sellings_delete():
    query = """
        DELETE FROM goods_movement g
        WHERE g.product_id = %s and g.affiliate_id = %s and g.goods_date = %s 
        RETURNING *
    """
    q_args = (
        request.args.get('product_id'),
        request.args.get('affiliate_id'),
        request.args.get('date')
    )        

    return jsonify(query_db(query, q_args, True)), 200

@app.route('/sellings/csv', methods=['GET'])
def sellings_save_csv():
    data = generate_csv(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args)
    return Response(data, mimetype='text/csv', headers={
        "Content-Disposition":"attachment;filename=report-sellings.csv"
    })

@app.route('/sellings/pdf', methods=['GET'])
def sellings_save_pdf():
    data = complex_table_request(SQL_SELLINGS_TABLE, SQL_SELLING_MASKS, request.args, paginate=False)
    for row in data:
        row.pop('product_id')
        row.pop('affiliate_id')

    html_template = render_template('pdf.html', data=data)
    pdf = pdfkit.from_string(html_template)
    return Response(pdf, mimetype='text/pdf', headers={
        "Content-Disposition":"attachment;filename=report-sellings.pdf"
    })

# -- Ассортимент --
SQL_ASSORTIMENT_TABLE = """
        SELECT a.affiliate_address "Магазин", p.product_name "Продукт", 
        s.stock_quantity "Количество", s.stock_price "Стоимость", s.stock_delivery "Ежедневная поставка",
        a.affiliate_id "affiliate_id", p.product_id "product_id"
        FROM stock s
        JOIN affiliate a on a.affiliate_id = s.affiliate_id
        JOIN product p on p.product_id = s.product_id
    """

SQL_ASSORTIMENT_MASK = {
    "product_id"     : "p.product_id", 
    "affiliate_id"   : "a.affiliate_id", 
    "stock_quantity" : "s.stock_quantity", 
    "stock_price"    : "s.stock_price", 
    "stock_delivery" : "s.stock_delivery"
}

class AssortimentForm(FlaskForm):
    ''' Форма заполнения информации об ассортименте '''
    product_id = SelectField(choices=[
        (x['product_id'], x['product_name']) for x in list_products_all()])
    affiliate_id = SelectField(choices=[
        (x['affiliate_id'], x['affiliate_address']) for x in list_affiliates_all()])
    stock_quantity = IntegerField(default=0, validators=[NumberRange(0)])
    stock_price = DecimalField(default = 0, validators=[NumberRange(0)])
    stock_delivery = IntegerField(default = 0, validators=[NumberRange(0)])
    submitForm = SubmitField('Сохранить')

@app.route('/assortiment', methods=['GET'])
def list_assortiment():
    queryData = complex_table_request(SQL_ASSORTIMENT_TABLE, SQL_ASSORTIMENT_MASK, request.args)
    # Разбиваем полученную таблицу (queryData) на записи (tableData) и составной PK (idData)
    tableData = []
    idData = []
    for row in queryData:
        product_id = row.pop('product_id')
        affiliate_id = row.pop('affiliate_id')
        tableData.append(row)
        idData.append({
            "product_id": product_id, 
            "affiliate_id": affiliate_id, 
        })
    arg_pagelimit = request.args.get('limit', type=int, default=RECORDS_PER_PAGE)
    app.logger.debug('QUERIED DATA')
    # tableData идёт в шаблон как элементы таблицы, idData размещается в атрибуте каждой строки
    return render_template('table.html', data=tableData, idData=idData, pages=(count_assortiment()[0]['count'] + arg_pagelimit - 1) // arg_pagelimit)


@app.route('/assortiment/count', methods=['GET'])
def count_assortiment():
    return complex_table_request(SQL_ASSORTIMENT_TABLE, SQL_ASSORTIMENT_MASK, request.args, True)

@app.route('/assortiment/add-form', methods=['GET', 'POST'])
def assortiment_create_form():
    form = AssortimentForm()
    if request.method == 'POST':
        if form.validate():
            query = """
                INSERT INTO public.stock
                (
                product_id, affiliate_id, 
                stock_quantity, stock_price, stock_delivery
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *; 
            """
            q_args = (
                form.product_id.data,
                form.affiliate_id.data,
                form.stock_quantity.data,
                form.stock_price.data,
                form.stock_delivery.data
            )

            return jsonify(query_db(query, q_args, True))
        else:
            return jsonify(form.errors), 400
    return render_template('assortiment_modal.html', form=form)

@app.route('/assortiment/functions', methods=['GET'])
def assortiment_input_form():
    form = AssortimentForm(meta={'csrf': False})
    return render_template('assortiment_func.html', form=form)

@app.route('/assortiment/edit-form', methods=['PUT'])
def assortiment_update_form():
    form = AssortimentForm(meta={'csrf': False})
    if form.validate():
        query = """
        UPDATE public.stock
        SET product_id=%s, affiliate_id=%s, stock_quantity=%s, stock_price=%s, stock_delivery=%s
        WHERE product_id=%s and affiliate_id=%s
        RETURNING *
        """
        
        q_args = (
            form.product_id.data,
            form.affiliate_id.data,
            form.stock_quantity.data,
            form.stock_price.data,
            form.stock_delivery.data,
            request.args.get('product_id'),
            request.args.get('affiliate_id'),
        )

        return jsonify(query_db(query, q_args, True))
    else:
        return jsonify(form.errors), 400

@app.route('/assortiment/del-form', methods=['DELETE'])
def assortiment_delete():
    query = """
        DELETE FROM stock s
        WHERE s.product_id = %s and s.affiliate_id = %s 
        RETURNING *
    """
    q_args = (
        request.args.get('product_id'),
        request.args.get('affiliate_id'),
    )        

    return jsonify(query_db(query, q_args, True)), 200

@app.route('/assortiment/csv', methods=['GET'])
def assortiment_save_csv():
    data = generate_csv(SQL_ASSORTIMENT_TABLE, SQL_ASSORTIMENT_MASK, request.args)
    return Response(data, mimetype='text/csv', headers={
        "Content-Disposition":"attachment;filename=report-stock.csv"
    })

@app.route('/assortiment/pdf', methods=['GET'])
def assortiment_save_pdf():
    data = complex_table_request(SQL_ASSORTIMENT_TABLE, SQL_ASSORTIMENT_MASK, request.args, paginate=False)
    for row in data:
        row.pop('product_id')
        row.pop('affiliate_id')

    html_template = render_template('pdf.html', data=data)
    pdf = pdfkit.from_string(html_template)
    return Response(pdf, mimetype='text/pdf', headers={
        "Content-Disposition":"attachment;filename=report-sellings.pdf"
    })



# -- Заказы --
SQL_ORDERS_TABLE = """
        SELECT pa.partner_name "Партнер", pr.product_name "Продукт", o.order_date "Дата",
        o.order_price "Стоимость", o.order_quantity "Количество", o.order_status "Статус",
        o.partner_id, o.product_id
        FROM "order" o
        JOIN partner pa ON pa.partner_id = o.partner_id
        JOIN product pr ON pr.product_id = o.product_id
    """

SQL_ORDERS_MASK = {
    "partner_id"   : "pa.partner_id", 
    "product_id"   : "pr.product_id", 
    "date"      : "o.order_date",
    "order_price" : "o.order_price", 
    "order_quantity": "o.order_quantity", 
    "order_status"    : "o.order_status"
}


class OrderForm(FlaskForm):
    ''' Форма заполнения информации о партнёре '''
    partner_id = SelectField(choices=[
        (x['partner_id'], x['partner_name']) for x in list_partners_all()
    ])
    product_id = SelectField(choices=[
        (x['product_id'], x['product_name']) for x in list_products_all()
    ])
    date = DateField(format="%Y-%m-%d", validators=[DataRequired()])
    order_price = DecimalField(default=0, validators=[NumberRange(0)])
    order_quantity = IntegerField(default=0, validators=[NumberRange(0)])
    order_status = SelectField(choices=['Выполнен', 'Одобрено', 'В процессе'])
    submitForm = SubmitField('Сохранить')


@app.route('/orders', methods=['GET'])
def list_orders():
    queryData = complex_table_request(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args)
    # Разбиваем полученную таблицу (queryData) на записи (tableData) и составной PK (idData)
    tableData = []
    idData = []
    for row in queryData:
        partner_id = row.pop('partner_id')
        product_id = row.pop('product_id')
        date_id = row['Дата']
        tableData.append(row)
        idData.append({
            "partner_id": partner_id, 
            "product_id": product_id, 
            "date": date_id
        })
    arg_pagelimit = request.args.get('limit', type=int, default=RECORDS_PER_PAGE)
    app.logger.debug('QUERIED DATA')
    # tableData идёт в шаблон как элементы таблицы, idData размещается в атрибуте каждой строки
    return render_template('table.html', data=tableData, idData=idData, pages=(count_orders()[0]['count'] + arg_pagelimit - 1) // arg_pagelimit)


@app.route('/orders/count', methods=['GET'])
def count_orders():
    ''' Подсчитываем количество записей по запросу с фильтрами '''
    return complex_table_request(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args, True)

@app.route('/orders/add-form', methods=['GET', 'POST'])
def orders_create_form():
    form = OrderForm()
    if request.method == 'POST':
        if form.validate():
            query = """
                INSERT INTO "order"
                (
                partner_id, product_id, 
                order_date, order_price, order_quantity, order_status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *; 
            """
            q_args = (
                form.partner_id.data,
                form.product_id.data,
                form.date.data,
                form.order_price.data,
                form.order_quantity.data,
                form.order_status.data
            )

            return jsonify(query_db(query, q_args, True))
        else:
            return jsonify(form.errors), 400
    return render_template('orders_modal.html', form=form)

@app.route('/orders/functions', methods=['GET'])
def orders_input_forms():
    form = OrderForm(meta={'csrf': False})
    return render_template('orders_func.html', form=form)

@app.route('/orders/edit-form', methods=['PUT'])
def orders_update_form():
    form = OrderForm(meta={'csrf': False})
    if form.validate():
        query = """
        UPDATE "order"
        SET partner_id=%s, product_id=%s, order_date=%s, order_price=%s, order_quantity=%s, order_status=%s
        WHERE partner_id=%s and product_id=%s and order_date=%s
        RETURNING *
        """
        
        q_args = (
            form.partner_id.data,
            form.product_id.data,
            form.date.data,
            form.order_price.data,
            form.order_quantity.data,
            form.order_status.data,
            request.args.get('partner_id'),
            request.args.get('product_id'),
            request.args.get('date')
        )

        return jsonify(query_db(query, q_args, True))
    else:
        return jsonify(form.errors), 400

@app.route('/orders/del-form', methods=['DELETE'])
def orders_delete():
    query = """
        DELETE FROM "order" p
        WHERE o.partner_id=%s and o.product_id = %s and o.order_date = %s 
        RETURNING *
    """
    q_args = (
        request.args.get('partner_id'),
        request.args.get('product_id'),
        request.args.get('date')
    )        

    return jsonify(query_db(query, q_args, True)), 200

@app.route('/orders/csv', methods=['GET'])
def orders_save_csv():
    data = generate_csv(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args)
    return Response(data, mimetype='text/csv', headers={
        "Content-Disposition":"attachment;filename=report-orders.csv"
    })

@app.route('/orders/pdf', methods=['GET'])
def orders_save_pdf():
    data = complex_table_request(SQL_ORDERS_TABLE, SQL_ORDERS_MASK, request.args, paginate=False)
    for row in data:
        row.pop('partner_id')
        row.pop('product_id')

    html_template = render_template('pdf.html', data=data)
    pdf = pdfkit.from_string(html_template)
    return Response(pdf, mimetype='text/pdf', headers={
        "Content-Disposition":"attachment;filename=report-orders.pdf"
    })


# Обрабатываем сигнал завершения 
def stop_server(signal=None, frame=None):
    print("Stopping server")
    sys.exit(0)


# ловушка для ручного закрытия контейнера
signal.signal(signal.SIGTERM, stop_server)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
    stop_server()